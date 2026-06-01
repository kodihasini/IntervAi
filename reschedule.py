"""
Smart Rescheduling for IntervAI
--------------------------------
Triggered when:
  - A candidate cancels  → free their slot, re-run CSP for that candidate
  - An interviewer becomes unavailable → re-assign all their booked slots

Strategy:
  1. Release affected assignments
  2. Re-run CSP on only the displaced candidates (minimal disruption)
  3. Return a diff of what changed
"""

from typing import Dict, List, Optional, Tuple
from .models import Candidate, Interviewer, TimeSlot, SlotStatus
from .csp import CSPScheduler


RescheduleResult = Dict[str, object]


class ReschedulingEngine:

    def __init__(
        self,
        candidates: Dict[str, Candidate],
        interviewers: Dict[str, Interviewer],
        slots: Dict[str, TimeSlot],
    ):
        self.candidates = candidates
        self.interviewers = interviewers
        self.slots = slots

    # ── Candidate cancels ─────────────────────────────────────────────

    def handle_candidate_cancellation(self, candidate_id: str) -> RescheduleResult:
        candidate = self.candidates.get(candidate_id)
        if not candidate:
            return {"success": False, "reason": "Candidate not found"}

        freed_slot_id = candidate.assigned_slot
        freed_iw_id = candidate.assigned_interviewer

        # Release
        self._release_candidate(candidate)

        return {
            "success": True,
            "event": "candidate_cancelled",
            "candidate": candidate_id,
            "freed_slot": freed_slot_id,
            "freed_interviewer": freed_iw_id,
            "changes": [],
        }

    # ── Interviewer becomes unavailable ───────────────────────────────

    def handle_interviewer_unavailable(
        self, interviewer_id: str
    ) -> RescheduleResult:
        interviewer = self.interviewers.get(interviewer_id)
        if not interviewer:
            return {"success": False, "reason": "Interviewer not found"}

        # Find all candidates assigned to this interviewer
        displaced: List[Candidate] = [
            c for c in self.candidates.values()
            if c.assigned_interviewer == interviewer_id
        ]

        if not displaced:
            return {
                "success": True,
                "event": "interviewer_unavailable",
                "interviewer": interviewer_id,
                "displaced_count": 0,
                "changes": [],
            }

        # Release their assignments
        for candidate in displaced:
            self._release_candidate(candidate)

        # Remove the unavailable interviewer's slots from their availability
        interviewer.available_slots = []

        # Re-run CSP for displaced candidates only
        solver = CSPScheduler(
            candidates=displaced,
            interviewers=list(self.interviewers.values()),
            slots=list(self.slots.values()),
        )
        new_assignment = solver.solve()

        changes = []
        if new_assignment:
            solver.apply_assignment(new_assignment)
            for cid, (sid, iid) in new_assignment.items():
                changes.append({
                    "candidate": cid,
                    "new_slot": sid,
                    "new_interviewer": iid,
                })
            unresolved = []
        else:
            unresolved = [c.candidate_id for c in displaced]

        return {
            "success": True,
            "event": "interviewer_unavailable",
            "interviewer": interviewer_id,
            "displaced_count": len(displaced),
            "rescheduled": len(changes),
            "unresolved": unresolved,
            "changes": changes,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _release_candidate(self, candidate: Candidate):
        """Free the slot and clear candidate's assignment."""
        if candidate.assigned_slot:
            slot = self.slots.get(candidate.assigned_slot)
            if slot:
                slot.status = SlotStatus.AVAILABLE
                slot.assigned_candidate = None
                slot.assigned_interviewer = None
        candidate.assigned_slot = None
        candidate.assigned_interviewer = None
