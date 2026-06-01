from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class Priority(Enum):
    VIP = 3
    NORMAL = 2
    LOW = 1


class SlotStatus(Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    CANCELLED = "cancelled"


@dataclass
class TimeSlot:
    slot_id: str
    start_time: str          # "09:00"
    end_time: str            # "09:30"
    date: str                # "2024-01-15"
    duration_minutes: int    # 30 or 60
    status: SlotStatus = SlotStatus.AVAILABLE
    assigned_candidate: Optional[str] = None
    assigned_interviewer: Optional[str] = None

    def to_dict(self):
        return {
            "slot_id": self.slot_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "date": self.date,
            "duration_minutes": self.duration_minutes,
            "status": self.status.value,
            "assigned_candidate": self.assigned_candidate,
            "assigned_interviewer": self.assigned_interviewer
        }


@dataclass
class Interviewer:
    interviewer_id: str
    name: str
    domains: List[str]           # e.g. ["backend", "system design"]
    available_slots: List[str]   # slot_ids

    def to_dict(self):
        return {
            "interviewer_id": self.interviewer_id,
            "name": self.name,
            "domains": self.domains,
            "available_slots": self.available_slots
        }


@dataclass
class Candidate:
    candidate_id: str
    name: str
    priority: Priority
    required_domain: str          # e.g. "backend"
    available_slots: List[str]    # slot_ids candidate is free
    confidence_scores: dict       # slot_id -> float (0.0 to 1.0)
    preferred_duration: int       # 30 or 60 minutes
    assigned_slot: Optional[str] = None
    assigned_interviewer: Optional[str] = None

    def to_dict(self):
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "priority": self.priority.name,
            "required_domain": self.required_domain,
            "available_slots": self.available_slots,
            "confidence_scores": self.confidence_scores,
            "preferred_duration": self.preferred_duration,
            "assigned_slot": self.assigned_slot,
            "assigned_interviewer": self.assigned_interviewer
        }
