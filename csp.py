"""
CSP Engine for IntervAI
-----------------------
Variables   : Candidates (each must be assigned a slot + interviewer)
Domains     : Valid (slot, interviewer) pairs per candidate
Constraints :
  1. Slot must be in candidate's available_slots
  2. Slot duration must match candidate's preferred_duration
  3. Interviewer must cover candidate's required_domain
  4. Interviewer must be free in that slot
  5. Slot must not already be booked
"""

from typing import Dict, List, Optional, Tuple
from .models import Candidate, Interviewer, TimeSlot, SlotStatus, Priority


Assignment = Dict[str, Tuple[str, str]]  # candidate_id -> (slot_id, interviewer_id)


class CSPScheduler:

    def __init__(
        self,
        candidates: List[Candidate],
        interviewers: List[Interviewer],
        slots: List[TimeSlot],
    ):
        self.candidates = {c.candidate_id: c for c in candidates}
        self.interviewers = {i.interviewer_id: i for i in interviewers}
        self.slots = {s.slot_id: s for s in slots}

        # Track which slots/interviewers are consumed during search
        self._booked_slots: set = set()
        self._interviewer_slot_used: set = set()  # (interviewer_id, slot_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self) -> Optional[Assignment]:
        """Run CSP backtracking and return a complete assignment or None."""
        ordered = self._order_candidates()
        assignment: Assignment = {}
        result = self._backtrack(ordered, 0, assignment)
        return result

    # ------------------------------------------------------------------
    # Backtracking
    # ------------------------------------------------------------------

    def _backtrack(
        self, ordered: List[Candidate], index: int, assignment: Assignment
    ) -> Optional[Assignment]:
        if index == len(ordered):
            return assignment  # All candidates assigned

        candidate = ordered[index]
        domain = self._build_domain(candidate)

        for slot_id, interviewer_id in domain:
            if self._is_consistent(candidate, slot_id, interviewer_id):
                # Assign
                assignment[candidate.candidate_id] = (slot_id, interviewer_id)
                self._booked_slots.add(slot_id)
                self._interviewer_slot_used.add((interviewer_id, slot_id))

                result = self._backtrack(ordered, index + 1, assignment)
                if result is not None:
                    return result

                # Undo
                del assignment[candidate.candidate_id]
                self._booked_slots.discard(slot_id)
                self._interviewer_slot_used.discard((interviewer_id, slot_id))

        return None  # No valid assignment for this candidate

    # ------------------------------------------------------------------
    # Domain & Constraint
    # ------------------------------------------------------------------

    def _build_domain(
        self, candidate: Candidate
    ) -> List[Tuple[str, str]]:
        """
        Return (slot_id, interviewer_id) pairs ordered by desirability.
        Ordering uses confidence score + priority score for smart slot picking.
        """
        pairs = []
        for slot_id in candidate.available_slots:
            slot = self.slots.get(slot_id)
            if slot is None:
                continue
            if slot.duration_minutes != candidate.preferred_duration:
                continue
            if slot.status != SlotStatus.AVAILABLE:
                continue

            for iw in self.interviewers.values():
                if candidate.required_domain not in iw.domains:
                    continue
                if slot_id not in iw.available_slots:
                    continue

                confidence = candidate.confidence_scores.get(slot_id, 0.5)
                # Score: confidence weighted by priority level
                score = confidence * candidate.priority.value
                pairs.append((slot_id, iw.interviewer_id, score))

        # Sort descending by score (best first)
        pairs.sort(key=lambda x: -x[2])
        return [(s, i) for s, i, _ in pairs]

    def _is_consistent(
        self, candidate: Candidate, slot_id: str, interviewer_id: str
    ) -> bool:
        """Check all constraints for a proposed assignment."""
        # Slot already booked by another candidate
        if slot_id in self._booked_slots:
            return False
        # Interviewer already used in this slot
        if (interviewer_id, slot_id) in self._interviewer_slot_used:
            return False
        return True

    # ------------------------------------------------------------------
    # Ordering heuristic: VIP first, then by number of options (MRV)
    # ------------------------------------------------------------------

    def _order_candidates(self) -> List[Candidate]:
        def sort_key(c: Candidate):
            domain_size = len(self._build_domain(c))
            # Higher priority first; within same priority, fewer options first (MRV)
            return (-c.priority.value, domain_size)

        return sorted(self.candidates.values(), key=sort_key)

    # ------------------------------------------------------------------
    # Apply final assignment back to objects
    # ------------------------------------------------------------------

    def apply_assignment(self, assignment: Assignment):
        for candidate_id, (slot_id, interviewer_id) in assignment.items():
            candidate = self.candidates[candidate_id]
            slot = self.slots[slot_id]

            candidate.assigned_slot = slot_id
            candidate.assigned_interviewer = interviewer_id
            slot.status = SlotStatus.BOOKED
            slot.assigned_candidate = candidate_id
            slot.assigned_interviewer = interviewer_id
