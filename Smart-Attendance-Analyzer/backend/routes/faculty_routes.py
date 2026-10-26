"""
routes/faculty_routes.py
==========================
Endpoints that power the Faculty Dashboard: institution-wide aggregates,
department/subject comparisons, defaulter lists, improving/declining
students, risk distribution, and the ability to drill into any individual
student's full record (faculty are not restricted to "their own" data the
way students are).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_faculty
from database import Attendance, Prediction, Student, Subject, User, get_db
from ml.predict import StudentFeatures, get_full_prediction
from models import (
    AttendanceEntryRecord,
    AttendanceStudentItem,
    BulkAttendanceInput,
    DepartmentStatOut,
    FacultyDashboardOut,
    MessageResponse,
    RiskDistributionOut,
    StudentDashboardOut,
    StudentProfileOut,
    StudentSummaryOut,
    SubjectAttendanceOut,
    SubjectOut,
    SubjectStatOut,
    WhatIfRequest,
    WhatIfResponse,
    WhatIfTrajectoryPoint,
)
from routes.student_routes import _get_attendance_records, _get_monthly_trend, _prediction_to_out

router = APIRouter(prefix="/api/faculty", tags=["Faculty"])

RISK_SEVERITY = {"Low Risk": 0, "Medium Risk": 1, "High Risk": 2}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def recalculate_and_predict_student(db: Session, student_id: int) -> None:
    """
    Recalculates student's overall attendance %, updates trend, extracts ML
    features, runs full AI risk prediction & forecast, and saves updated
    Prediction record and Attendance risk_labels.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return

    records = db.query(Attendance).filter(Attendance.student_id == student_id).all()
    if not records:
        return

    total_pct = sum(r.attendance_percentage for r in records)
    overall_pct = round(total_pct / len(records), 2)

    avg_prev = sum(r.previous_attendance_percentage or 0.0 for r in records) / len(records)
    if overall_pct - avg_prev > 1.5:
        trend = "improving"
    elif avg_prev - overall_pct > 1.5:
        trend = "declining"
    else:
        trend = "stable"

    student.overall_attendance_percentage = overall_pct
    student.trend = trend

    leaves = sum(r.leaves_taken for r in records) / len(records)
    marks = sum(r.internal_marks or 0 for r in records) / len(records)
    monthly = sum(r.monthly_attendance or 0.0 for r in records) / len(records)

    weakest = min(records, key=lambda r: r.attendance_percentage)
    weakest_subj = weakest.subject.name if weakest.attendance_percentage < 75 and weakest.subject else None

    features = StudentFeatures(
        current_attendance=overall_pct,
        previous_attendance=round(avg_prev, 2),
        leaves_taken=int(round(leaves)),
        internal_marks=int(round(marks)),
        distance_km=student.distance_km or 0.0,
        monthly_attendance=round(monthly, 2),
    )

    try:
        ml_res = get_full_prediction(
            features=features,
            avg_leaves=leaves,
            avg_internal_marks=marks,
            weakest_subject=weakest_subj,
        )

        predicted_risk = ml_res["predicted_risk_level"]
        for r in records:
            if r.attendance_percentage < 65:
                r.risk_label = "High Risk"
            elif r.attendance_percentage < 75:
                r.risk_label = "Medium Risk" if predicted_risk != "High Risk" else "High Risk"
            else:
                r.risk_label = predicted_risk

        prediction_entry = Prediction(
            student_id=student.id,
            predicted_risk_level=predicted_risk,
            risk_model_used=ml_res["risk_model_used"],
            forecast_attendance_percentage=ml_res["forecast_attendance_percentage"],
            forecast_model_used=ml_res["forecast_model_used"],
            cluster_segment=ml_res["cluster_segment"],
            ai_recommendation=json.dumps(ml_res["ai_recommendations"]),
        )
        db.add(prediction_entry)
        db.commit()
    except Exception as exc:
        db.commit()


def _compute_worst_case_risk(db: Session, student_ids: Optional[List[int]] = None) -> Dict[int, str]:
    """
    Compute each student's "headline" risk level as the most severe risk
    label across any of their enrolled subjects (a student at High Risk
    in even one subject is flagged High Risk overall -- the conservative,
    actionable choice for a faculty-facing warning system).
    """
    query = db.query(Attendance.student_id, Attendance.risk_label)
    if student_ids is not None:
        query = query.filter(Attendance.student_id.in_(student_ids))

    worst: Dict[int, str] = {}
    for student_id, risk_label in query.all():
        if not risk_label:
            continue
        current = worst.get(student_id)
        if current is None or RISK_SEVERITY.get(risk_label, 0) > RISK_SEVERITY.get(current, 0):
            worst[student_id] = risk_label
    return worst


def _to_summary(student: Student, risk_map: Dict[int, str], db: Optional[Session] = None) -> StudentSummaryOut:
    forecast_val = None
    if db:
        latest_pred = (
            db.query(Prediction)
            .filter(Prediction.student_id == student.id)
            .order_by(Prediction.created_at.desc())
            .first()
        )
        if latest_pred:
            forecast_val = latest_pred.forecast_attendance_percentage

    return StudentSummaryOut(
        student_code=student.student_code,
        name=student.name,
        department=student.department,
        semester=student.semester,
        overall_attendance_percentage=student.overall_attendance_percentage,
        trend=student.trend,
        risk_level=risk_map.get(student.id),
        forecast_attendance_percentage=forecast_val,
    )


def _department_stats(db: Session) -> List[DepartmentStatOut]:
    rows = (
        db.query(Student.department, func.avg(Student.overall_attendance_percentage), func.count(Student.id))
        .group_by(Student.department)
        .all()
    )
    stats = []
    for dept, avg_attendance, count in rows:
        below_75 = (
            db.query(func.count(Student.id))
            .filter(Student.department == dept, Student.overall_attendance_percentage < 75)
            .scalar()
        )
        stats.append(
            DepartmentStatOut(
                department=dept,
                average_attendance=round(float(avg_attendance or 0), 2),
                total_students=count,
                below_75_count=below_75 or 0,
            )
        )
    return sorted(stats, key=lambda s: s.average_attendance)


def _subject_stats(db: Session, department: Optional[str] = None) -> List[SubjectStatOut]:
    query = (
        db.query(Subject.name, func.avg(Attendance.attendance_percentage), func.count(Attendance.id))
        .join(Attendance, Attendance.subject_id == Subject.id)
    )
    if department:
        query = query.join(Student, Attendance.student_id == Student.id).filter(Student.department == department)
    rows = query.group_by(Subject.name).all()

    return sorted(
        [
            SubjectStatOut(subject_name=name, average_attendance=round(float(avg or 0), 2), total_enrolled=count)
            for name, avg, count in rows
        ],
        key=lambda s: s.average_attendance,
    )


def _base_student_query(db: Session, department: Optional[str] = None, semester: Optional[int] = None):
    query = db.query(Student)
    if department:
        query = query.filter(Student.department == department)
    if semester:
        query = query.filter(Student.semester == semester)
    return query


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@router.get("/dashboard", response_model=FacultyDashboardOut)
def get_faculty_dashboard(
    department: Optional[str] = Query(None, description="Filter to a single department; omit for institution-wide view"),
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> FacultyDashboardOut:
    """
    Aggregate payload powering the entire Faculty Dashboard page: totals,
    below-75% count, department/subject comparisons, top defaulters,
    improving/declining students, and overall risk distribution.
    """
    base_query = _base_student_query(db, department=department)

    total_students = base_query.count()
    if total_students == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No students found for this filter")

    students_below_75 = base_query.filter(Student.overall_attendance_percentage < 75).count()

    attendance_stats = base_query.with_entities(
        func.max(Student.overall_attendance_percentage),
        func.min(Student.overall_attendance_percentage),
        func.avg(Student.overall_attendance_percentage),
    ).first()
    highest, lowest, average = attendance_stats

    department_stats = _department_stats(db) if not department else [
        s for s in _department_stats(db) if s.department == department
    ]
    subject_stats = _subject_stats(db, department=department)

    # Top 10 defaulters (lowest attendance, excluding students with no attendance data yet)
    defaulter_rows = (
        base_query.filter(Student.overall_attendance_percentage > 0)
        .order_by(Student.overall_attendance_percentage.asc())
        .limit(10)
        .all()
    )

    improving_rows = (
        base_query.filter(Student.trend == "improving")
        .order_by(Student.overall_attendance_percentage.desc())
        .limit(10)
        .all()
    )
    declining_rows = (
        base_query.filter(Student.trend == "declining")
        .order_by(Student.overall_attendance_percentage.asc())
        .limit(10)
        .all()
    )

    relevant_ids = [s.id for s in defaulter_rows + improving_rows + declining_rows]
    risk_map = _compute_worst_case_risk(db, student_ids=relevant_ids)

    # Risk distribution across ALL students matching the filter
    all_ids = [s.id for s in base_query.all()]
    full_risk_map = _compute_worst_case_risk(db, student_ids=all_ids)
    risk_counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    for risk in full_risk_map.values():
        if risk in risk_counts:
            risk_counts[risk] += 1

    return FacultyDashboardOut(
        total_students=total_students,
        students_below_75=students_below_75,
        highest_attendance=round(float(highest or 0), 2),
        lowest_attendance=round(float(lowest or 0), 2),
        average_attendance=round(float(average or 0), 2),
        department_stats=department_stats,
        subject_stats=subject_stats,
        top_defaulters=[_to_summary(s, risk_map) for s in defaulter_rows],
        students_improving=[_to_summary(s, risk_map) for s in improving_rows],
        students_declining=[_to_summary(s, risk_map) for s in declining_rows],
        risk_distribution=RiskDistributionOut(
            low_risk=risk_counts["Low Risk"],
            medium_risk=risk_counts["Medium Risk"],
            high_risk=risk_counts["High Risk"],
        ),
    )


@router.get("/students", response_model=List[StudentSummaryOut])
def list_students(
    department: Optional[str] = None,
    semester: Optional[int] = None,
    search: Optional[str] = Query(None, description="Search by name or student code"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> List[StudentSummaryOut]:
    """Paginated, filterable, searchable list of all students."""
    query = _base_student_query(db, department=department, semester=semester)
    if search:
        like_pattern = f"%{search.strip()}%"
        query = query.filter((Student.name.ilike(like_pattern)) | (Student.student_code.ilike(like_pattern)))

    rows = query.order_by(Student.student_code).offset(skip).limit(limit).all()
    risk_map = _compute_worst_case_risk(db, student_ids=[s.id for s in rows])

    return [_to_summary(s, risk_map) for s in rows]


@router.get("/students/{student_code}", response_model=StudentDashboardOut)
def get_student_detail(
    student_code: str,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> StudentDashboardOut:
    """Full drill-down view of a single student, for faculty inspection."""
    student = db.query(Student).filter(Student.student_code == student_code.upper()).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student '{student_code}' not found")

    records = _get_attendance_records(db, student.id)
    subject_wise = [
        SubjectAttendanceOut(
            subject_name=r.subject.name,
            total_classes=r.total_classes,
            classes_attended=r.classes_attended,
            attendance_percentage=r.attendance_percentage,
            leaves_taken=r.leaves_taken,
            internal_marks=r.internal_marks,
            risk_label=r.risk_label,
        )
        for r in records
    ]
    overall_attendance = (
        round(sum(r.attendance_percentage for r in records) / len(records), 2) if records else 0.0
    )
    total_leaves = sum(r.leaves_taken for r in records)
    avg_marks = (
        round(sum(r.internal_marks for r in records if r.internal_marks is not None) / len(records), 2)
        if records else None
    )
    monthly_trend = _get_monthly_trend(db, student.id)

    latest_prediction_row = (
        db.query(Prediction)
        .filter(Prediction.student_id == student.id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    latest_prediction = _prediction_to_out(latest_prediction_row)
    if latest_prediction:
        latest_prediction.student_code = student.student_code

    return StudentDashboardOut(
        profile=StudentProfileOut.model_validate(student),
        overall_attendance_percentage=overall_attendance,
        subject_wise=subject_wise,
        monthly_trend=monthly_trend,
        total_leaves=total_leaves,
        average_internal_marks=avg_marks,
        latest_prediction=latest_prediction,
    )


@router.get("/below-75", response_model=List[StudentSummaryOut])
def get_students_below_75(
    department: Optional[str] = None,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> List[StudentSummaryOut]:
    """All students currently below the 75% attendance requirement."""
    rows = (
        _base_student_query(db, department=department)
        .filter(Student.overall_attendance_percentage < 75)
        .order_by(Student.overall_attendance_percentage.asc())
        .all()
    )
    risk_map = _compute_worst_case_risk(db, student_ids=[s.id for s in rows])
    return [_to_summary(s, risk_map) for s in rows]


@router.get("/top-defaulters", response_model=List[StudentSummaryOut])
def get_top_defaulters(
    limit: int = Query(10, ge=1, le=50),
    department: Optional[str] = None,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> List[StudentSummaryOut]:
    """The N students with the lowest attendance percentage."""
    rows = (
        _base_student_query(db, department=department)
        .filter(Student.overall_attendance_percentage > 0)
        .order_by(Student.overall_attendance_percentage.asc())
        .limit(limit)
        .all()
    )
    risk_map = _compute_worst_case_risk(db, student_ids=[s.id for s in rows])
    return [_to_summary(s, risk_map, db=db) for s in rows]


# --------------------------------------------------------------------------
# Faculty Data Entry & Interactive Tools
# --------------------------------------------------------------------------

@router.get("/subjects", response_model=List[SubjectOut])
def get_subjects(
    department: Optional[str] = Query(None),
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> List[SubjectOut]:
    """List available subjects, optionally filtered by department."""
    query = db.query(Subject)
    if department:
        query = query.filter(Subject.department == department)
    rows = query.order_by(Subject.name).all()
    return [SubjectOut(id=s.id, name=s.name, department=s.department) for s in rows]


@router.get("/students-for-attendance", response_model=List[AttendanceStudentItem])
def get_students_for_attendance(
    department: str,
    semester: int,
    subject_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> List[AttendanceStudentItem]:
    """List students in a department/semester with current attendance in the chosen subject."""
    students = (
        db.query(Student)
        .filter(Student.department == department, Student.semester == semester)
        .order_by(Student.student_code)
        .all()
    )

    result = []
    for s in students:
        att = (
            db.query(Attendance)
            .filter(Attendance.student_id == s.id, Attendance.subject_id == subject_id)
            .first()
        )
        result.append(
            AttendanceStudentItem(
                student_id=s.id,
                student_code=s.student_code,
                name=s.name,
                overall_attendance_percentage=s.overall_attendance_percentage,
                classes_attended=att.classes_attended if att else 0,
                total_classes=att.total_classes if att else 0,
                subject_attendance_percentage=att.attendance_percentage if att else 0.0,
            )
        )
    return result


@router.post("/record-attendance", response_model=MessageResponse)
def record_attendance(
    payload: BulkAttendanceInput,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Record attendance for a class session. Updates total_classes & classes_attended,
    recalculates subject and overall percentages, and automatically triggers ML
    risk predictions for all affected students!
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    updated_count = 0
    student_ids_to_update = set()

    for item in payload.records:
        att = (
            db.query(Attendance)
            .filter(Attendance.student_id == item.student_id, Attendance.subject_id == payload.subject_id)
            .first()
        )
        if not att:
            # Create attendance record if it doesn't exist yet
            att = Attendance(
                student_id=item.student_id,
                subject_id=payload.subject_id,
                total_classes=1,
                classes_attended=1 if item.present else 0,
                attendance_percentage=100.0 if item.present else 0.0,
                previous_attendance_percentage=75.0,
                leaves_taken=0 if item.present else 1,
                internal_marks=70,
                monthly_attendance=100.0 if item.present else 0.0,
            )
            db.add(att)
        else:
            att.previous_attendance_percentage = att.attendance_percentage
            att.total_classes += 1
            if item.present:
                att.classes_attended += 1
            else:
                att.leaves_taken += 1
            att.attendance_percentage = round((att.classes_attended / att.total_classes) * 100.0, 2)

        updated_count += 1
        student_ids_to_update.add(item.student_id)

    db.commit()

    # Automatically re-run ML risk analysis & predictions for all affected students
    for s_id in student_ids_to_update:
        recalculate_and_predict_student(db, s_id)

    return MessageResponse(
        message=f"Successfully recorded attendance for {updated_count} students in {subject.name}. AI risk models updated!"
    )


@router.post("/upload-csv-attendance", response_model=MessageResponse)
async def upload_csv_attendance(
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Upload CSV attendance file (student_code, name, status).
    Validates IDs, updates records, recalculates percentages, and runs ML risk analysis!
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    contents = await file.read()
    csv_text = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(csv_text))

    updated_count = 0
    student_ids_to_update = set()

    for row in reader:
        # Standardize CSV column names
        code = row.get("student_code") or row.get("Student_ID") or row.get("student_id") or row.get("Code")
        status_str = row.get("status") or row.get("Status") or row.get("attendance")

        if not code or not status_str:
            continue

        student = db.query(Student).filter(Student.student_code == code.strip().upper()).first()
        if not student:
            continue

        is_present = status_str.strip().lower() in ["present", "p", "1", "true", "yes"]

        att = (
            db.query(Attendance)
            .filter(Attendance.student_id == student.id, Attendance.subject_id == subject_id)
            .first()
        )
        if not att:
            att = Attendance(
                student_id=student.id,
                subject_id=subject_id,
                total_classes=1,
                classes_attended=1 if is_present else 0,
                attendance_percentage=100.0 if is_present else 0.0,
                previous_attendance_percentage=75.0,
                leaves_taken=0 if is_present else 1,
                internal_marks=70,
                monthly_attendance=100.0 if is_present else 0.0,
            )
            db.add(att)
        else:
            att.previous_attendance_percentage = att.attendance_percentage
            att.total_classes += 1
            if is_present:
                att.classes_attended += 1
            else:
                att.leaves_taken += 1
            att.attendance_percentage = round((att.classes_attended / att.total_classes) * 100.0, 2)

        updated_count += 1
        student_ids_to_update.add(student.id)

    db.commit()

    for s_id in student_ids_to_update:
        recalculate_and_predict_student(db, s_id)

    return MessageResponse(
        message=f"Successfully processed CSV. Updated attendance for {updated_count} students in {subject.name}. AI risk models updated!"
    )


@router.post("/what-if", response_model=WhatIfResponse)
def run_what_if_simulation(
    payload: WhatIfRequest,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> WhatIfResponse:
    """
    What-If simulation tool for faculty to test attendance recovery or drop scenarios.
    Computes trajectory of percentage changes and updated risk levels.
    """
    student = db.query(Student).filter(Student.student_code == payload.student_code.upper()).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student '{payload.student_code}' not found")

    records = db.query(Attendance).filter(Attendance.student_id == student.id).all()
    if not records:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No attendance records available for simulation")

    total_cls = sum(r.total_classes for r in records)
    att_cls = sum(r.classes_attended for r in records)
    curr_pct = round((att_cls / max(total_cls, 1)) * 100.0, 2)

    # Classes needed for 75%
    # (att_cls + N) / (total_cls + N) >= 0.75 => N >= ceil(3*total_cls - 4*att_cls)
    needed = max(0, int(round(3 * total_cls - 4 * att_cls))) if curr_pct < 75.0 else 0

    # Simulate future trajectory
    # Attending attend_next classes OR missing miss_next classes
    trajectory: List[WhatIfTrajectoryPoint] = []
    trajectory.append(WhatIfTrajectoryPoint(step=0, label="Current Status", percentage=curr_pct))

    sim_total = total_cls
    sim_att = att_cls

    if payload.attend_next > 0:
        step_size = max(1, payload.attend_next // 4)
        curr_step = 0
        while curr_step < payload.attend_next:
            curr_step = min(payload.attend_next, curr_step + step_size)
            proj = round(((att_cls + curr_step) / (total_cls + curr_step)) * 100.0, 2)
            trajectory.append(WhatIfTrajectoryPoint(step=curr_step, label=f"+{curr_step} attended", percentage=proj))
        sim_total = total_cls + payload.attend_next
        sim_att = att_cls + payload.attend_next
    elif payload.miss_next > 0:
        step_size = max(1, payload.miss_next // 4)
        curr_step = 0
        while curr_step < payload.miss_next:
            curr_step = min(payload.miss_next, curr_step + step_size)
            proj = round(((att_cls) / (total_cls + curr_step)) * 100.0, 2)
            trajectory.append(WhatIfTrajectoryPoint(step=curr_step, label=f"+{curr_step} missed", percentage=proj))
        sim_total = total_cls + payload.miss_next
        sim_att = att_cls

    projected_pct = round((sim_att / max(sim_total, 1)) * 100.0, 2)

    # Determine risk level
    def get_risk(pct: float) -> str:
        if pct < 65:
            return "High Risk"
        elif pct < 75:
            return "Medium Risk"
        return "Low Risk"

    curr_risk = get_risk(curr_pct)
    proj_risk = get_risk(projected_pct)

    return WhatIfResponse(
        student_code=student.student_code,
        name=student.name,
        current_percentage=curr_pct,
        projected_percentage=projected_pct,
        current_risk_level=curr_risk,
        projected_risk_level=proj_risk,
        classes_needed_for_75=needed,
        trajectory=trajectory,
    )

