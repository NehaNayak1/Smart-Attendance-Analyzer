"""
routes/prediction_routes.py
=============================
Endpoints that expose the three trained ML models (risk classification,
attendance forecast, student segmentation) plus the rule-based AI
recommendation engine, via `ml/predict.py`.

Access rules for POST /predict and GET /history/{student_code}:
    - A student may only request predictions for THEMSELVES.
    - Faculty/admin may request predictions for any student, or supply
      manual feature values for a hypothetical "what-if" scenario with no
      linked student_code (in which case nothing is persisted to the DB).
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import Attendance, Prediction, Student, User, get_db
from models import (
    PredictionHistoryOut,
    PredictionOut,
    PredictionRequest,
    RoleEnum,
    AStarRecoveryPlanOut,
    AStarRecoveryRequest,
    AStarRecoveryResponse,
    AStarStepOut,
    AStarSubjectBreakdownOut,
    BackwardChainQueryRequest,
    BackwardChainQueryResponse,
    HillClimbingAllocationItem,
    HillClimbingOptimizeRequest,
    HillClimbingOptimizeResponse,
    HillClimbingTrajectoryPoint,
    KnowledgeRuleOut,
)
from ml.predict import StudentFeatures, get_full_prediction
from ml.ai_search import a_star_recovery_planner, hill_climbing_attendance_optimizer
from ml.knowledge_engine import (
    DEFAULT_RULES,
    backward_chain,
    extract_facts_from_features,
)

router = APIRouter(prefix="/api/prediction", tags=["Prediction"])

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_DIR = os.path.join(BACKEND_DIR, "ml", "metrics")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _resolve_target_student(db: Session, current_user: User, requested_code: Optional[str]) -> Optional[Student]:
    """
    Apply access-control rules and resolve which Student (if any) this
    prediction request is about.
    """
    if current_user.role == RoleEnum.student.value:
        own_student = current_user.student
        if not own_student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No student profile linked to this account")
        if requested_code and requested_code.upper() != own_student.student_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students may only request predictions for their own profile",
            )
        return own_student

    # Faculty / admin
    if requested_code:
        student = db.query(Student).filter(Student.student_code == requested_code.upper()).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student '{requested_code}' not found")
        return student

    return None  # hypothetical / manual scenario, no linked student


def _build_features_from_student(db: Session, student: Student) -> tuple[StudentFeatures, float, float, Optional[str]]:
    """
    Aggregate a student's per-subject attendance records into a single
    feature snapshot (averaged across subjects), plus the weakest subject
    name (used for a targeted recommendation).
    """
    records = db.query(Attendance).filter(Attendance.student_id == student.id).join(Attendance.subject).all()
    if not records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No attendance data available yet for student '{student.student_code}'",
        )

    current_attendance = sum(r.attendance_percentage for r in records) / len(records)
    previous_attendance = sum(r.previous_attendance_percentage or 0 for r in records) / len(records)
    leaves_taken = sum(r.leaves_taken for r in records) / len(records)
    internal_marks = sum(r.internal_marks or 0 for r in records) / len(records)
    monthly_attendance = sum(r.monthly_attendance or 0 for r in records) / len(records)

    weakest = min(records, key=lambda r: r.attendance_percentage)
    weakest_subject = weakest.subject.name if weakest.attendance_percentage < 75 else None

    features = StudentFeatures(
        current_attendance=round(current_attendance, 2),
        previous_attendance=round(previous_attendance, 2),
        leaves_taken=int(round(leaves_taken)),
        internal_marks=int(round(internal_marks)),
        distance_km=student.distance_km or 0.0,
        monthly_attendance=round(monthly_attendance, 2),
    )
    return features, leaves_taken, internal_marks, weakest_subject


def _build_features_from_manual(payload: PredictionRequest) -> tuple[StudentFeatures, float, float, None]:
    """Validate and build a feature snapshot from manually supplied values."""
    required = [
        payload.current_attendance,
        payload.previous_attendance,
        payload.leaves_taken,
        payload.internal_marks,
        payload.distance_km,
        payload.monthly_attendance,
    ]
    if any(v is None for v in required):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Either provide 'student_code', or supply all manual feature values: "
                "current_attendance, previous_attendance, leaves_taken, internal_marks, "
                "distance_km, monthly_attendance"
            ),
        )
    features = StudentFeatures(
        current_attendance=payload.current_attendance,
        previous_attendance=payload.previous_attendance,
        leaves_taken=payload.leaves_taken,
        internal_marks=payload.internal_marks,
        distance_km=payload.distance_km,
        monthly_attendance=payload.monthly_attendance,
    )
    return features, float(payload.leaves_taken), float(payload.internal_marks), None


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@router.post("/predict", response_model=PredictionOut)
def predict(
    payload: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionOut:
    """
    Run all three ML models (risk classification, attendance forecast,
    segmentation) for either a specific student or a manually-specified
    hypothetical scenario, and return the combined result with AI
    recommendations. Persists a Prediction record when a student is linked.
    """
    student = _resolve_target_student(db, current_user, payload.student_code)

    if student is not None:
        features, avg_leaves, avg_marks, weakest_subject = _build_features_from_student(db, student)
    else:
        features, avg_leaves, avg_marks, weakest_subject = _build_features_from_manual(payload)

    result = get_full_prediction(
        features=features,
        avg_leaves=avg_leaves,
        avg_internal_marks=avg_marks,
        weakest_subject=weakest_subject,
    )

    prediction_out = PredictionOut(
        student_code=student.student_code if student else None,
        predicted_risk_level=result["predicted_risk_level"],
        risk_model_used=result["risk_model_used"],
        risk_confidence=result["risk_confidence"],
        forecast_attendance_percentage=result["forecast_attendance_percentage"],
        forecast_model_used=result["forecast_model_used"],
        cluster_segment=result["cluster_segment"],
        ai_recommendations=result["ai_recommendations"],
        created_at=None,
    )

    if student is not None:
        db_prediction = Prediction(
            student_id=student.id,
            predicted_risk_level=result["predicted_risk_level"],
            risk_model_used=result["risk_model_used"],
            forecast_attendance_percentage=result["forecast_attendance_percentage"],
            forecast_model_used=result["forecast_model_used"],
            cluster_segment=result["cluster_segment"],
            ai_recommendation=json.dumps(result["ai_recommendations"]),
        )
        db.add(db_prediction)
        db.commit()
        db.refresh(db_prediction)
        prediction_out.created_at = db_prediction.created_at

    return prediction_out


@router.get("/history/{student_code}", response_model=PredictionHistoryOut)
def get_prediction_history(
    student_code: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionHistoryOut:
    """Return the most recent predictions saved for a given student."""
    student = _resolve_target_student(db, current_user, student_code)
    if student is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid student_code is required")

    rows = (
        db.query(Prediction)
        .filter(Prediction.student_id == student.id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )

    history: List[PredictionOut] = []
    for row in rows:
        try:
            recs = json.loads(row.ai_recommendation) if row.ai_recommendation else []
        except (json.JSONDecodeError, TypeError):
            recs = [row.ai_recommendation] if row.ai_recommendation else []

        history.append(
            PredictionOut(
                student_code=student.student_code,
                predicted_risk_level=row.predicted_risk_level,
                risk_model_used=row.risk_model_used,
                risk_confidence=None,
                forecast_attendance_percentage=row.forecast_attendance_percentage,
                forecast_model_used=row.forecast_model_used,
                cluster_segment=row.cluster_segment,
                ai_recommendations=recs,
                created_at=row.created_at,
            )
        )

    return PredictionHistoryOut(student_code=student.student_code, history=history)


@router.get("/model-info")
def get_model_info(current_user: User = Depends(get_current_user)) -> dict:
    """
    Return the saved training metrics for all three models (accuracy,
    precision, recall, F1, ROC-AUC, MAE, RMSE, R2, silhouette score, etc)
    so the frontend can render an "About the Models" transparency panel.
    """
    result = {}
    for key, filename in [
        ("risk_model", "risk_model_metrics.json"),
        ("forecast_model", "forecast_model_metrics.json"),
        ("segmentation_model", "segmentation_model_metrics.json"),
    ]:
        path = os.path.join(METRICS_DIR, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                result[key] = json.load(f)
        else:
            result[key] = None

    return result


# --------------------------------------------------------------------------
# Classical AI Algorithm Endpoints (Module 3 & Module 4)
# --------------------------------------------------------------------------

def _extract_subject_dicts(
    db: Session,
    current_user: User,
    student_code: Optional[str],
    subjects_input: Optional[List[Any]],
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Helper to extract a list of subject dictionaries from live student or manual input."""
    if subjects_input:
        return [
            {
                "subject_id": s.subject_id,
                "name": s.name,
                "classes_attended": s.classes_attended,
                "total_classes": s.total_classes,
                "difficulty_weight": s.difficulty_weight,
                "internal_marks": s.internal_marks or 50.0,
            }
            for s in subjects_input
        ], student_code

    if student_code:
        student = _resolve_target_student(db, current_user, student_code)
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student '{student_code}' not found")
        records = db.query(Attendance).filter(Attendance.student_id == student.id).join(Attendance.subject).all()
        if not records:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No attendance records for {student_code}")
        return [
            {
                "subject_id": r.subject_id,
                "name": r.subject.name,
                "classes_attended": r.classes_attended,
                "total_classes": r.total_classes,
                "difficulty_weight": 1.2 if (r.internal_marks or 50) < 50 else 1.0,
                "internal_marks": r.internal_marks or 50.0,
            }
            for r in records
        ], student.student_code

    # Default to logged-in student if student role
    if current_user.role == RoleEnum.student.value and current_user.student:
        return _extract_subject_dicts(db, current_user, current_user.student.student_code, None)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either supply 'student_code' or provide a list of 'subjects'",
    )


@router.post("/ai/a-star-recovery", response_model=AStarRecoveryResponse)
def run_a_star_recovery(
    payload: AStarRecoveryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AStarRecoveryResponse:
    """
    Module 3 (Lecture 16): A* Search Algorithm.
    Finds the mathematically optimal, minimum-effort sequence of classes
    a student must attend across subjects to satisfy the target percentage.
    """
    subjects, code = _extract_subject_dicts(db, current_user, payload.student_code, payload.subjects)
    raw_plan = a_star_recovery_planner(subjects, target_percentage=payload.target_percentage)

    plan_out = AStarRecoveryPlanOut(
        algorithm=raw_plan["algorithm"],
        target_percentage=raw_plan["target_percentage"],
        achieved=raw_plan["achieved"],
        total_classes_to_attend=raw_plan["total_classes_to_attend"],
        total_effort_cost=raw_plan["total_effort_cost"],
        nodes_explored=raw_plan["nodes_explored"],
        steps=[AStarStepOut(**s) for s in raw_plan["steps"]],
        subject_breakdown=[AStarSubjectBreakdownOut(**b) for b in raw_plan["subject_breakdown"]],
    )
    return AStarRecoveryResponse(student_code=code, plan=plan_out)


@router.post("/ai/hill-climbing-optimize", response_model=HillClimbingOptimizeResponse)
def run_hill_climbing_optimization(
    payload: HillClimbingOptimizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HillClimbingOptimizeResponse:
    """
    Module 3 (Lecture 19): Steepest-Ascent Hill Climbing Search.
    Finds the optimal allocation of a constrained attendance budget (K classes)
    across subjects to maximize overall academic safety and minimize detention penalties.
    """
    subjects, code = _extract_subject_dicts(db, current_user, payload.student_code, payload.subjects)
    result = hill_climbing_attendance_optimizer(subjects, attendance_budget=payload.attendance_budget)

    return HillClimbingOptimizeResponse(
        algorithm=result["algorithm"],
        student_code=code,
        attendance_budget=result["attendance_budget"],
        iterations=result["iterations"],
        initial_score=result["initial_score"],
        optimized_score=result["optimized_score"],
        score_improvement=result["score_improvement"],
        allocations=[HillClimbingAllocationItem(**a) for a in result["allocations"]],
        convergence_trajectory=[HillClimbingTrajectoryPoint(**p) for p in result["convergence_trajectory"]],
    )


@router.post("/ai/backward-chain-query", response_model=BackwardChainQueryResponse)
def run_backward_chaining_query(
    payload: BackwardChainQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BackwardChainQueryResponse:
    """
    Module 4 (Lecture 23): Backward Chaining Inference (Goal-Driven).
    Tests whether a hypothesis/goal (e.g., 'exam_eligibility_cleared',
    'academic_probation_risk', 'high_exam_detention_risk') can be logically proven
    from student facts and institutional regulations.
    """
    # Resolve student facts
    if payload.student_code:
        student = _resolve_target_student(db, current_user, payload.student_code)
        features, leaves, marks, _ = _build_features_from_student(db, student)
        code = student.student_code
    elif payload.manual_features:
        features, leaves, marks, _ = _build_features_from_manual(payload.manual_features)
        code = None
    elif current_user.role == RoleEnum.student.value and current_user.student:
        student = current_user.student
        features, leaves, marks, _ = _build_features_from_student(db, student)
        code = student.student_code
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 'student_code' or 'manual_features' to query backward chaining",
        )

    facts = extract_facts_from_features(
        current_attendance=features.current_attendance,
        previous_attendance=features.previous_attendance,
        leaves_taken=features.leaves_taken,
        internal_marks=features.internal_marks,
        distance_km=features.distance_km,
        monthly_attendance=features.monthly_attendance,
    )

    proved, proof_tree, missing = backward_chain(payload.target_goal, facts)

    return BackwardChainQueryResponse(
        algorithm="Backward Chaining Inference (Goal-Driven)",
        student_code=code,
        target_goal=payload.target_goal,
        proved=proved,
        proof_tree=proof_tree,
        missing_facts=missing,
        current_known_facts=sorted(list(facts)),
    )


@router.get("/ai/knowledge-rules", response_model=List[KnowledgeRuleOut])
def list_knowledge_rules(current_user: User = Depends(get_current_user)) -> List[KnowledgeRuleOut]:
    """
    Module 4: Inspect the Knowledge Base rules (Horn clauses) used by the
    Forward and Backward Chaining engines.
    """
    return [
        KnowledgeRuleOut(
            rule_id=r.rule_id,
            name=r.name,
            antecedents=r.antecedents,
            consequent=r.consequent,
            recommendation=r.recommendation,
            explanation=r.explanation,
        )
        for r in DEFAULT_RULES
    ]
