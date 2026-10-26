"""
ai_search.py
============
Classical Artificial Intelligence Search Algorithms (Module 3).

Implements:
1. A* Search Algorithm (Module 3, Lecture 16):
   - Optimal Multi-Subject Attendance Recovery Path Planning.
   - Formulated as state-space heuristic search f(n) = g(n) + h(n).
   - Finds the least-effort sequence of classes a student must attend across
     subjects to satisfy attendance criteria (>= 75% per subject / overall).
   - Uses an admissible and consistent heuristic h(n) ensuring optimality.

2. Steepest-Ascent Hill Climbing Search (Module 3, Lecture 19):
   - Attendance Budget & Schedule Optimizer.
   - Formulated as local search to allocate a constrained attendance capacity K
     across N subjects to maximize academic standing and minimize detention risk.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# 1. A* Search Algorithm: Multi-Subject Attendance Recovery Planner
# ==============================================================================

@dataclass(frozen=True)
class SubjectState:
    """State of an individual subject in the search space."""
    subject_id: int
    name: str
    attended: int
    total: int
    difficulty_weight: float = 1.0  # effort multiplier (1.0 = standard, 1.5 = heavy lab)

    @property
    def percentage(self) -> float:
        if self.total <= 0:
            return 100.0
        return round((self.attended / self.total) * 100.0, 2)

    def classes_needed_for(self, target_pct: float = 75.0) -> int:
        """
        Minimum additional classes needed with 100% attendance:
        (attended + n) / (total + n) >= target_pct / 100
        n * (1 - target) >= target * total - attended
        n >= (target * total - attended) / (1 - target)
        """
        target = target_pct / 100.0
        if target >= 1.0:
            return 0
        deficit = target * self.total - self.attended
        if deficit <= 0:
            return 0
        import math
        return math.ceil(deficit / (1.0 - target))


@dataclass(order=True)
class AStarNode:
    """Priority queue node for A* search ordered by f(n) = g(n) + h(n), breaking ties with h(n)."""
    f_cost: float
    h_cost: float  # Tie-breaker: smaller h (closer to goal) is prioritized
    g_cost: float = field(compare=False)
    state: Tuple[Tuple[int, int], ...] = field(compare=False)  # tuple of ((attended, total), ...)
    action: Optional[str] = field(default=None, compare=False)
    parent: Optional[Any] = field(default=None, compare=False)
    last_idx: int = field(default=0, compare=False)


def _heuristic(
    state_tuples: Tuple[Tuple[int, int], ...],
    target_pct: float,
    weights: List[float],
) -> float:
    """
    Admissible Heuristic h(n):
    Calculates the theoretical minimum weighted effort to bring all deficit
    subjects up to target_pct.
    Since each action step can only attend at most 1 class in 1 subject,
    h(n) <= h*(n) (never overestimates the true remaining cost), guaranteeing
    that A* search returns an optimal, minimum-effort recovery plan.
    """
    target = target_pct / 100.0
    h = 0.0
    import math

    for (att, tot), weight in zip(state_tuples, weights):
        deficit = target * tot - att
        if deficit > 0:
            needed = math.ceil(deficit / (1.0 - target))
            h += needed * weight
    return h


def a_star_recovery_planner(
    subjects: List[Dict[str, Any]],
    target_percentage: float = 75.0,
    max_nodes: int = 10000,
) -> Dict[str, Any]:
    """
    Runs the A* Search Algorithm to find the optimal attendance recovery path.

    Parameters:
        subjects: list of dicts with keys:
                  'id' or 'subject_id', 'name', 'classes_attended', 'total_classes',
                  and optional 'difficulty_weight' (default 1.0).
        target_percentage: minimum attendance target per subject (default 75.0%).
        max_nodes: exploration safety budget to prevent excessive search space expansion.

    Returns:
        Structured recovery plan including optimal action steps, nodes explored,
        total classes to attend, and per-subject breakdown.
    """
    if not subjects:
        return {
            "algorithm": "A* Heuristic Search",
            "target_percentage": target_percentage,
            "achieved": True,
            "total_classes_to_attend": 0,
            "total_effort_cost": 0.0,
            "nodes_explored": 0,
            "steps": [],
            "subject_breakdown": [],
        }

    subject_names = [str(s.get("name") or s.get("subject_name") or f"Subject-{i+1}") for i, s in enumerate(subjects)]
    weights = [float(s.get("difficulty_weight", 1.0)) for s in subjects]

    # Initial state representation: tuple of ((attended, total), ...)
    initial_state_tuples = tuple(
        (int(s.get("classes_attended", 0)), int(s.get("total_classes", 0)))
        for s in subjects
    )

    initial_h = _heuristic(initial_state_tuples, target_percentage, weights)

    # Goal test helper: check if all subjects meet or exceed the target percentage
    def is_goal(state_t: Tuple[Tuple[int, int], ...]) -> bool:
        for att, tot in state_t:
            if tot > 0:
                pct = (att / tot) * 100.0
                if round(pct, 2) < target_pct_threshold:
                    return False
        return True

    target_pct_threshold = target_percentage - 1e-4

    # If already meeting goal
    if is_goal(initial_state_tuples):
        return {
            "algorithm": "A* Heuristic Search",
            "target_percentage": target_percentage,
            "achieved": True,
            "total_classes_to_attend": 0,
            "total_effort_cost": 0.0,
            "nodes_explored": 1,
            "steps": [],
            "subject_breakdown": [
                {
                    "subject": name,
                    "current_percentage": round((att / max(tot, 1)) * 100.0, 2),
                    "classes_needed": 0,
                    "projected_percentage": round((att / max(tot, 1)) * 100.0, 2),
                }
                for name, (att, tot) in zip(subject_names, initial_state_tuples)
            ],
        }

    # Open set (Priority Queue) and Closed set (Visited state table with lowest g)
    open_heap: List[AStarNode] = []
    start_node = AStarNode(
        f_cost=initial_h,
        g_cost=0.0,
        h_cost=initial_h,
        state=initial_state_tuples,
        action=None,
        parent=None,
    )
    heapq.heappush(open_heap, start_node)

    best_g: Dict[Tuple[Tuple[int, int], ...], float] = {initial_state_tuples: 0.0}
    nodes_explored = 0
    goal_node: Optional[AStarNode] = None

    while open_heap and nodes_explored < max_nodes:
        current = heapq.heappop(open_heap)
        nodes_explored += 1

        # Check goal condition
        if is_goal(current.state):
            goal_node = current
            break

        # If we already found a cheaper route to this state, skip
        if current.g_cost > best_g.get(current.state, float("inf")):
            continue

        # Expand successors: for each subject that is still below the threshold
        # Using canonical ordering (idx >= current.last_idx) to eliminate commutative permutations
        for idx in range(current.last_idx, len(subjects)):
            att, tot = current.state[idx]
            curr_pct = (att / max(tot, 1)) * 100.0
            if curr_pct >= target_pct_threshold:
                continue  # already satisfied this subject, prioritize deficit ones

            # Successor state: student attends 1 upcoming class in this subject
            new_state_list = list(current.state)
            new_state_list[idx] = (att + 1, tot + 1)
            new_state = tuple(new_state_list)

            step_cost = weights[idx]
            tentative_g = current.g_cost + step_cost

            if tentative_g < best_g.get(new_state, float("inf")):
                best_g[new_state] = tentative_g
                h = _heuristic(new_state, target_percentage, weights)
                f = tentative_g + h
                action_desc = f"Attend upcoming lecture in '{subject_names[idx]}'"
                successor = AStarNode(
                    f_cost=f,
                    g_cost=tentative_g,
                    h_cost=h,
                    state=new_state,
                    action=action_desc,
                    parent=current,
                    last_idx=idx,
                )
                heapq.heappush(open_heap, successor)

    # Reconstruct path from goal_node back to start
    steps: List[Dict[str, Any]] = []
    curr = goal_node
    final_state = goal_node.state if goal_node else initial_state_tuples

    while curr and curr.parent:
        steps.append({
            "step_number": 0,  # will reverse and index
            "action": curr.action,
            "cumulative_g_cost": round(curr.g_cost, 2),
        })
        curr = curr.parent

    steps.reverse()
    for i, s in enumerate(steps, 1):
        s["step_number"] = i

    # Per-subject breakdown
    subject_breakdown = []
    total_classes_to_attend = 0
    for idx, name in enumerate(subject_names):
        init_att, init_tot = initial_state_tuples[idx]
        fin_att, fin_tot = final_state[idx]
        added = fin_att - init_att
        total_classes_to_attend += added
        subject_breakdown.append({
            "subject": name,
            "initial_percentage": round((init_att / max(init_tot, 1)) * 100.0, 2),
            "classes_needed": added,
            "projected_percentage": round((fin_att / max(fin_tot, 1)) * 100.0, 2),
        })

    return {
        "algorithm": "A* Heuristic Search (f(n) = g(n) + h(n))",
        "target_percentage": target_percentage,
        "achieved": goal_node is not None,
        "total_classes_to_attend": total_classes_to_attend,
        "total_effort_cost": round(goal_node.g_cost, 2) if goal_node else 0.0,
        "nodes_explored": nodes_explored,
        "steps": steps,
        "subject_breakdown": subject_breakdown,
    }


# ==============================================================================
# 2. Steepest-Ascent Hill Climbing: Attendance Budget Optimizer
# ==============================================================================

def _evaluate_allocation(
    allocation: List[int],
    initial_attended: List[int],
    initial_total: List[int],
    marks_weights: List[float],
) -> float:
    """
    Objective / Evaluation Function E(s) to maximize:
    Higher score represents safer academic standing and reduced detention risk.
    Penalties are heavily assigned to subjects remaining under 65% (Critical)
    or under 75% (Detention boundary).
    """
    score = 0.0
    for alloc, init_att, init_tot, mark_w in zip(
        allocation, initial_attended, initial_total, marks_weights
    ):
        proj_att = init_att + alloc
        proj_tot = init_tot + alloc
        pct = (proj_att / max(proj_tot, 1)) * 100.0

        # Base satisfaction
        score += pct * mark_w

        # Threshold bonuses and penalties
        if pct >= 75.0:
            score += 50.0  # Safe zone bonus
        elif pct >= 65.0:
            score -= (75.0 - pct) * 2.0  # Medium risk linear penalty
        else:
            score -= 100.0 + (65.0 - pct) * 5.0  # Critical risk severe penalty

    return round(score, 3)


def hill_climbing_attendance_optimizer(
    subjects: List[Dict[str, Any]],
    attendance_budget: int,
    max_iterations: int = 100,
) -> Dict[str, Any]:
    """
    Runs Steepest-Ascent Hill Climbing to find the optimal allocation of a
    constrained attendance capacity (budget K) across subjects.

    Parameters:
        subjects: list of dicts with subject stats.
        attendance_budget: total number of classes the student is able to attend.
        max_iterations: limit to prevent endless plateaus.

    Returns:
        Optimized distribution of classes across subjects, initial vs best score,
        and convergence trajectory.
    """
    n_subjects = len(subjects)
    if n_subjects == 0 or attendance_budget <= 0:
        return {
            "algorithm": "Steepest-Ascent Hill Climbing Search",
            "attendance_budget": attendance_budget,
            "iterations": 0,
            "initial_score": 0.0,
            "optimized_score": 0.0,
            "allocations": [],
        }

    subject_names = [str(s.get("name") or s.get("subject_name") or f"Subject-{i+1}") for i, s in enumerate(subjects)]
    init_attended = [int(s.get("classes_attended", 0)) for s in subjects]
    init_total = [int(s.get("total_classes", 0)) for s in subjects]
    # Internal marks used as relative importance weights (normalized around 1.0)
    marks = [float(s.get("internal_marks") or 50.0) for s in subjects]
    avg_mark = sum(marks) / max(len(marks), 1)
    marks_weights = [round(m / max(avg_mark, 1.0), 2) for m in marks]

    # Initial state: distribute budget uniformly across subjects
    base_alloc = attendance_budget // n_subjects
    remainder = attendance_budget % n_subjects
    current_state = [base_alloc] * n_subjects
    for r in range(remainder):
        current_state[r] += 1

    current_score = _evaluate_allocation(
        current_state, init_attended, init_total, marks_weights
    )
    initial_score = current_score

    trajectory = [{"iteration": 0, "score": current_score, "allocation": list(current_state)}]

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        best_neighbor = None
        best_neighbor_score = current_score

        # Generate neighborhood: transfer 1 attendance unit from subject i to subject j
        for i in range(n_subjects):
            if current_state[i] <= 0:
                continue
            for j in range(n_subjects):
                if i == j:
                    continue
                neighbor = list(current_state)
                neighbor[i] -= 1
                neighbor[j] += 1

                neighbor_score = _evaluate_allocation(
                    neighbor, init_attended, init_total, marks_weights
                )
                if neighbor_score > best_neighbor_score:
                    best_neighbor_score = neighbor_score
                    best_neighbor = neighbor

        # Steepest-Ascent condition: if no neighbor strictly improves the evaluation function,
        # we have reached a local or global optimum (peak)
        if best_neighbor is None or best_neighbor_score <= current_score:
            break

        current_state = best_neighbor
        current_score = best_neighbor_score
        trajectory.append({
            "iteration": iteration,
            "score": current_score,
            "allocation": list(current_state),
        })

    # Prepare readable output
    allocations = []
    for idx in range(n_subjects):
        alloc = current_state[idx]
        cur_pct = round((init_attended[idx] / max(init_total[idx], 1)) * 100.0, 2)
        proj_pct = round(((init_attended[idx] + alloc) / max(init_total[idx] + alloc, 1)) * 100.0, 2)
        allocations.append({
            "subject": subject_names[idx],
            "current_percentage": cur_pct,
            "allocated_classes": alloc,
            "projected_percentage": proj_pct,
            "status": "Safe" if proj_pct >= 75.0 else ("Medium Risk" if proj_pct >= 65.0 else "Critical Risk"),
        })

    return {
        "algorithm": "Steepest-Ascent Hill Climbing Search",
        "attendance_budget": attendance_budget,
        "iterations": iteration,
        "initial_score": initial_score,
        "optimized_score": current_score,
        "score_improvement": round(current_score - initial_score, 3),
        "allocations": allocations,
        "convergence_trajectory": trajectory,
    }
