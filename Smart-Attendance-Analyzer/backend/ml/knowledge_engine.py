"""
knowledge_engine.py
===================
Knowledge Representation & Reasoning (Module 4, Lecture 23).

Implements:
1. Production Rule Knowledge Base (Horn Clauses)
2. Forward Chaining Inference Engine (Data-Driven Reasoning)
3. Backward Chaining Goal Verification Engine (Goal-Driven Reasoning)

Used to analyze student academic attendance, diagnose root causes of risk,
verify institutional goals (e.g. Exam Eligibility, Academic Probation),
and deduce formally-grounded, explainable recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class KnowledgeRule:
    """
    Represents a Horn Clause rule:
    IF antecedent_1 AND antecedent_2 AND ... THEN consequent
    """
    rule_id: str
    name: str
    antecedents: List[str]
    consequent: str
    recommendation: Optional[str] = None
    explanation: Optional[str] = None


# ==============================================================================
# Domain Knowledge Base (Institutional Attendance & Academic Regulations)
# ==============================================================================

DEFAULT_RULES: List[KnowledgeRule] = [
    KnowledgeRule(
        rule_id="R1",
        name="Detention Risk Due to Downward Trajectory",
        antecedents=["attendance_below_75", "trend_declining"],
        consequent="high_exam_detention_risk",
        recommendation="You are at imminent risk of exam detention due to a declining attendance trajectory. Immediate intervention required.",
        explanation="Student is currently below 75% attendance and attendance rate is actively declining.",
    ),
    KnowledgeRule(
        rule_id="R2",
        name="Active Recovery Trajectory",
        antecedents=["attendance_below_75", "trend_improving"],
        consequent="attendance_recovering",
        recommendation="Your attendance is currently below 75% but trending upward. Maintain your current attendance streak.",
        explanation="Student attendance is below 75% but improving compared to last semester/month.",
    ),
    KnowledgeRule(
        rule_id="R3",
        name="Academic Probation Alert",
        antecedents=["high_exam_detention_risk", "internal_marks_low"],
        consequent="academic_probation_risk",
        recommendation="Dual risk detected: Low attendance combined with low internal marks places you in academic probation jeopardy.",
        explanation="Low attendance is directly compounding poor test performance.",
    ),
    KnowledgeRule(
        rule_id="R4",
        name="Commute-Induced Absenteeism",
        antecedents=["commute_long", "leaves_high"],
        consequent="transport_distress_factor",
        recommendation="Long transit distance is impacting regular attendance. Consider college transport, carpool, or hostel accommodations.",
        explanation="Student lives > 15 km away and has accumulated high leaves.",
    ),
    KnowledgeRule(
        rule_id="R5",
        name="Habitual Absenteeism",
        antecedents=["commute_normal", "leaves_high"],
        consequent="habitual_absenteeism_risk",
        recommendation="High absence rate without transit impediments detected. Review personal leave habits to prevent disciplinary notice.",
        explanation="High leaves taken despite living within standard college commuting distance.",
    ),
    KnowledgeRule(
        rule_id="R6",
        name="Mandatory Faculty Counseling Required",
        antecedents=["high_exam_detention_risk"],
        consequent="action_mandatory_advisor_meeting",
        recommendation="Schedule a mandatory advisory session with your department academic counselor this week.",
        explanation="Regulations require counseling once detention risk is confirmed.",
    ),
    KnowledgeRule(
        rule_id="R7",
        name="Remedial Tutoring Assignment",
        antecedents=["academic_probation_risk"],
        consequent="action_schedule_remedial_tutoring",
        recommendation="Enroll in department remedial tutoring classes to recover internal evaluation marks.",
        explanation="Academic probation requires remedial support intervention.",
    ),
    KnowledgeRule(
        rule_id="R8",
        name="Critical Attendance Emergency",
        antecedents=["attendance_critical_below_65"],
        consequent="parent_guardian_notification_required",
        recommendation="Attendance is critically below 65%. Official communication will be dispatched to parent/guardian.",
        explanation="Attendance has dropped below the statutory 65% condonation threshold.",
    ),
    KnowledgeRule(
        rule_id="R9",
        name="Exam Eligibility Guaranteed",
        antecedents=["attendance_satisfactory", "trend_stable_or_positive"],
        consequent="exam_eligibility_cleared",
        recommendation="You are in full compliance with semester attendance requirements. Exam hall ticket clearance approved.",
        explanation="Attendance is >= 75% and trajectory is stable or positive.",
    ),
    KnowledgeRule(
        rule_id="R10",
        name="Academic Dean's List Contender",
        antecedents=["attendance_satisfactory", "internal_marks_high"],
        consequent="dean_honor_roll_candidate",
        recommendation="Outstanding performance: High attendance and top marks qualify you for semester academic honors.",
        explanation="Attendance is above threshold and internal evaluation exceeds 75 marks.",
    ),
]


class KnowledgeBase:
    """Manages rules and facts for forward and backward inference."""

    def __init__(self, rules: Optional[List[KnowledgeRule]] = None) -> None:
        self.rules = rules or list(DEFAULT_RULES)

    def get_rules_for_consequent(self, goal: str) -> List[KnowledgeRule]:
        return [r for r in self.rules if r.consequent == goal]


# ==============================================================================
# Fact Extraction from Student Features
# ==============================================================================

def extract_facts_from_features(
    current_attendance: float,
    previous_attendance: float,
    leaves_taken: int,
    internal_marks: int,
    distance_km: float,
    monthly_attendance: Optional[float] = None,
) -> Set[str]:
    """
    Maps continuous numeric features into symbolic logical propositions
    suitable for propositional knowledge representation.
    """
    facts: Set[str] = set()

    # Attendance thresholds
    if current_attendance < 65.0:
        facts.add("attendance_critical_below_65")
        facts.add("attendance_below_75")
    elif current_attendance < 75.0:
        facts.add("attendance_below_75")
    else:
        facts.add("attendance_satisfactory")

    # Trend propositions
    trend = current_attendance - previous_attendance
    if monthly_attendance is not None:
        recent_trend = current_attendance - monthly_attendance
    else:
        recent_trend = trend

    if trend < -2.0 or recent_trend < -2.0:
        facts.add("trend_declining")
    elif trend > 2.0 or recent_trend > 2.0:
        facts.add("trend_improving")
    else:
        facts.add("trend_stable_or_positive")

    # Leaves propositions
    if leaves_taken >= 10:
        facts.add("leaves_high")
    else:
        facts.add("leaves_moderate")

    # Internal marks propositions
    if internal_marks < 50:
        facts.add("internal_marks_low")
    elif internal_marks >= 75:
        facts.add("internal_marks_high")
    else:
        facts.add("internal_marks_average")

    # Distance propositions
    if distance_km >= 15.0:
        facts.add("commute_long")
    else:
        facts.add("commute_normal")

    return facts


# ==============================================================================
# 1. Forward Chaining Inference Engine (Data-Driven)
# ==============================================================================

def forward_chain(
    initial_facts: Set[str],
    kb: Optional[KnowledgeBase] = None,
) -> Dict[str, Any]:
    """
    Executes Forward Chaining inference:
    Iteratively fires rules whose antecedents are satisfied by known facts,
    adding consequents to working memory until no new facts can be derived.

    Returns:
        dict with:
        - derived_facts: all proven facts
        - fired_rules: sequence of rules fired with explanations
        - recommendations: list of actionable guidance strings derived from fired rules
        - risk_diagnoses: list of key diagnostic conclusions
    """
    if kb is None:
        kb = KnowledgeBase()

    working_memory = set(initial_facts)
    fired_rules: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    fired_rule_ids: Set[str] = set()

    iteration = 0
    while True:
        iteration += 1
        new_fact_derived = False

        for rule in kb.rules:
            if rule.rule_id in fired_rule_ids:
                continue

            # Check if all antecedents are present in working memory
            if all(ante in working_memory for ante in rule.antecedents):
                fired_rule_ids.add(rule.rule_id)
                working_memory.add(rule.consequent)
                new_fact_derived = True

                fired_rules.append({
                    "rule_id": rule.rule_id,
                    "rule_name": rule.name,
                    "antecedents_satisfied": rule.antecedents,
                    "consequent_derived": rule.consequent,
                    "explanation": rule.explanation,
                })

                if rule.recommendation:
                    recommendations.append(rule.recommendation)

        if not new_fact_derived:
            break

    # Extract high-level diagnoses
    diagnostic_tags = [
        "high_exam_detention_risk",
        "academic_probation_risk",
        "transport_distress_factor",
        "habitual_absenteeism_risk",
        "exam_eligibility_cleared",
        "dean_honor_roll_candidate",
        "attendance_recovering",
        "parent_guardian_notification_required",
    ]
    diagnoses = [d for d in diagnostic_tags if d in working_memory]

    return {
        "algorithm": "Forward Chaining Inference (Data-Driven)",
        "iterations": iteration,
        "initial_facts": sorted(list(initial_facts)),
        "derived_facts": sorted(list(working_memory)),
        "fired_rules": fired_rules,
        "recommendations": recommendations,
        "risk_diagnoses": diagnoses,
    }


# ==============================================================================
# 2. Backward Chaining Goal Verification Engine (Goal-Driven)
# ==============================================================================

def backward_chain(
    goal: str,
    known_facts: Set[str],
    kb: Optional[KnowledgeBase] = None,
    visited_goals: Optional[Set[str]] = None,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    Executes Backward Chaining reasoning to verify if a target academic goal
    can be logically proven from current facts and rules.

    Parameters:
        goal: target proposition (e.g., 'exam_eligibility_cleared', 'academic_probation_risk')
        known_facts: set of currently observed student facts
        kb: KnowledgeBase instance

    Returns:
        (proved: bool, proof_tree: dict, missing_facts: list)
    """
    if kb is None:
        kb = KnowledgeBase()
    if visited_goals is None:
        visited_goals = set()

    # Base Case 1: Goal is already a known ground fact
    if goal in known_facts:
        return True, {"goal": goal, "status": "KNOWN_GROUND_FACT"}, []

    # Cycle detection
    if goal in visited_goals:
        return False, {"goal": goal, "status": "CYCLE_DETECTED"}, [goal]

    visited_goals.add(goal)

    # Base Case 2: Find all rules that conclude this goal
    matching_rules = kb.get_rules_for_consequent(goal)
    if not matching_rules:
        return False, {"goal": goal, "status": "UNPROVABLE_NO_MATCHING_RULE"}, [goal]

    # Try to prove any rule that has goal as consequent (OR over candidate rules)
    overall_missing: List[str] = []
    for rule in matching_rules:
        rule_subgoals_proven = True
        subproofs: List[Dict[str, Any]] = []
        rule_missing: List[str] = []

        # All antecedents of this rule must be proven (AND over antecedents)
        for antecedent in rule.antecedents:
            proven, subproof, missing = backward_chain(
                antecedent, known_facts, kb, visited_goals.copy()
            )
            subproofs.append(subproof)
            if not proven:
                rule_subgoals_proven = False
                rule_missing.extend(missing)

        if rule_subgoals_proven:
            return True, {
                "goal": goal,
                "status": "PROVEN",
                "via_rule": rule.rule_id,
                "rule_name": rule.name,
                "subproofs": subproofs,
            }, []

        overall_missing.extend(rule_missing)

    return False, {
        "goal": goal,
        "status": "NOT_PROVEN",
        "attempted_rules": [r.rule_id for r in matching_rules],
    }, list(set(overall_missing))
