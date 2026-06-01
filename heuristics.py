"""
Heuristics for IntervAI
-----------------------
1. FairnessChecker  – ensures no single group monopolises morning/afternoon slots
2. ConfidenceEvaluator – scores an assignment by its average confidence
3. PrioritySlotAllocator – pre-labels slots as "preferred" for VIP candidates
"""

from typing import Dict, List, Tuple
from .models import Candidate, TimeSlot, Priority


# ── 1. Fairness ────────────────────────────────────────────────────────────────

class FairnessChecker:
    """
    Constraint: no more than `max_ratio` of morning (or afternoon) slots
    should go to the same priority group.

    Morning  : start_time < "12:00"
    Afternoon: start_time >= "12:00"
    """

    def __init__(self, max_ratio: float = 0.6):
        self.max_ratio = max_ratio

    def check(
        self,
        assignment: Dict[str, Tuple[str, str]],
        candidates: Dict[str, Candidate],
        slots: Dict[str, TimeSlot],
    ) -> Dict[str, object]:
        morning_counts: Dict[str, int] = {p.name: 0 for p in Priority}
        afternoon_counts: Dict[str, int] = {p.name: 0 for p in Priority}
        total_morning = 0
        total_afternoon = 0

        for cid, (sid, _) in assignment.items():
            slot = slots[sid]
            priority_name = candidates[cid].priority.name
            if slot.start_time < "12:00":
                morning_counts[priority_name] += 1
                total_morning += 1
            else:
                afternoon_counts[priority_name] += 1
                total_afternoon += 1

        violations = []
        for p in Priority:
            if total_morning > 0:
                ratio = morning_counts[p.name] / total_morning
                if ratio > self.max_ratio:
                    violations.append(
                        f"{p.name} candidates hold {ratio:.0%} of morning slots "
                        f"(limit {self.max_ratio:.0%})"
                    )
            if total_afternoon > 0:
                ratio = afternoon_counts[p.name] / total_afternoon
                if ratio > self.max_ratio:
                    violations.append(
                        f"{p.name} candidates hold {ratio:.0%} of afternoon slots "
                        f"(limit {self.max_ratio:.0%})"
                    )

        return {
            "fair": len(violations) == 0,
            "violations": violations,
            "morning_distribution": morning_counts,
            "afternoon_distribution": afternoon_counts,
        }


# ── 2. Confidence Evaluator ────────────────────────────────────────────────────

class ConfidenceEvaluator:
    """Score an assignment by average availability confidence."""

    def score(
        self,
        assignment: Dict[str, Tuple[str, str]],
        candidates: Dict[str, Candidate],
    ) -> Dict[str, object]:
        if not assignment:
            return {"average_confidence": 0.0, "per_candidate": {}}

        per_candidate = {}
        total = 0.0
        for cid, (sid, _) in assignment.items():
            conf = candidates[cid].confidence_scores.get(sid, 0.5)
            per_candidate[cid] = round(conf, 2)
            total += conf

        avg = total / len(assignment)
        return {
            "average_confidence": round(avg, 3),
            "per_candidate": per_candidate,
        }


# ── 3. Priority Slot Annotator ─────────────────────────────────────────────────

def annotate_preferred_slots(
    slots: List[TimeSlot],
    candidates: List[Candidate],
) -> Dict[str, List[str]]:
    """
    Returns a dict mapping priority level -> list of slot_ids that are
    considered 'preferred' for that priority.

    Rule:
      VIP    -> earliest slots of the day
      NORMAL -> mid-day slots
      LOW    -> late-day or remaining slots
    """
    sorted_slots = sorted(slots, key=lambda s: (s.date, s.start_time))
    n = len(sorted_slots)
    third = max(1, n // 3)

    preferred: Dict[str, List[str]] = {
        Priority.VIP.name: [s.slot_id for s in sorted_slots[:third]],
        Priority.NORMAL.name: [s.slot_id for s in sorted_slots[third: 2 * third]],
        Priority.LOW.name: [s.slot_id for s in sorted_slots[2 * third:]],
    }
    return preferred
