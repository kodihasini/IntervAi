# IntervAI — Automated Interview Slot Scheduler

> A constraint-based intelligent scheduling system built with Python + Flask, demonstrating core AI concepts: **state-space problem formulation**, **CSP with backtracking**, **MRV/LCV heuristics**, **fairness reasoning**, and **dynamic rescheduling**.

---

## Quick Start

```bash
git clone https://github.com/your-username/intervai.git
cd intervai
pip install -r requirements.txt
python app.py
```

Open your browser at **http://localhost:5000**

> **Requirements:** Python 3.9+ — No external database needed (SQLite is built into Python)

---

## What IntervAI Does

IntervAI schedules candidates to interview slots with matching interviewers — automatically. Given a set of candidates (with priorities, domain requirements, availability, and confidence scores), interviewers (with domain expertise and availability), and time slots, the system finds a valid, fair, and optimal assignment using AI reasoning techniques.

It also handles real-world disruptions: if a candidate cancels or an interviewer becomes unavailable, the system re-runs scheduling only for the affected candidates with minimal disruption.

---

## CO Mapping — How This Project Covers Each Outcome

### CO1 · Problem Formulation & Knowledge Representation
**File:** `scheduler/models.py`, `app.py`

The scheduling problem is formulated as a classical AI state-space problem:

| Component | IntervAI Representation |
|---|---|
| **Variables** | Each candidate that must be assigned |
| **State** | Current (candidate → slot, interviewer) mapping |
| **Actions** | Assign or unassign a (slot, interviewer) pair |
| **Goal** | All candidates assigned with no constraint violations |
| **Cost** | Confidence score × priority weight |

Knowledge is represented using Python dataclasses (`Candidate`, `Interviewer`, `TimeSlot`), enums (`Priority`, `SlotStatus`), and dictionaries for constraint lookups — directly applying graph/rule-based representation from CO1.

```python
# models.py — typed state representation
@dataclass
class Candidate:
    candidate_id: str
    priority: Priority          # VIP=3, NORMAL=2, LOW=1
    required_domain: str        # constraint for interviewer matching
    confidence_scores: dict     # slot_id -> float (0.0 to 1.0)
    preferred_duration: int     # hard constraint on slot duration
```

---

### CO2 · Search Algorithms & Heuristics
**File:** `scheduler/csp.py` → `_build_domain()`, `_order_candidates()`

The CSP solver uses an informed search strategy. The domain for each candidate is built and **sorted by a score combining confidence and priority**, functioning as a heuristic to guide the backtracking search toward better solutions first:

```python
score = confidence * candidate.priority.value
pairs.sort(key=lambda x: -x[2])  # best-first ordering
```

This is analogous to how A* uses f(n) = g(n) + h(n) to prefer promising nodes. The solver expands the most-likely-to-succeed assignment before backtracking — reducing unnecessary search.

---

### CO3 · Constraint Satisfaction (CSP)
**Files:** `scheduler/csp.py`, `scheduler/heuristics.py`

This is the **core AI module**. The scheduler is a fully implemented CSP engine:

**Variables:** Candidates  
**Domains:** Valid (slot, interviewer) pairs per candidate  
**Constraints (all enforced in `_is_consistent`):**
1. Slot must be in candidate's available slots
2. Slot duration must match candidate's preferred duration
3. Interviewer must cover candidate's required domain
4. Interviewer must be free in that slot
5. Slot must not already be booked

**Heuristics applied:**

| Heuristic | Where Used | Effect |
|---|---|---|
| **MRV** (Minimum Remaining Values) | `_order_candidates()` | Candidates with fewer valid options are scheduled first |
| **Priority ordering** | `_order_candidates()` | VIP candidates scheduled before NORMAL and LOW |
| **Confidence-weighted LCV** | `_build_domain()` | Slots that score highest for a candidate are tried first |

**Backtracking with undo:**
```python
# Assign → recurse → undo if it fails
assignment[candidate.candidate_id] = (slot_id, interviewer_id)
self._booked_slots.add(slot_id)
result = self._backtrack(ordered, index + 1, assignment)
if result is None:
    del assignment[candidate.candidate_id]   # backtrack
    self._booked_slots.discard(slot_id)
```

**Explainability:** When no valid schedule is found, the API returns a clear message: `"No valid schedule found. Check that slots, domains, and durations are compatible."` — directly addressing the CO3 requirement for constraint failure explainability.

---

### CO4 · Decision Making & Policy Selection
**Files:** `scheduler/heuristics.py` → `FairnessChecker`, `scheduler/reschedule.py`

The system makes **utility-based decisions** when selecting the best assignment. Each (slot, interviewer) pair is scored using:

```
utility(slot, candidate) = confidence_score × priority_weight
```

This directly models the utility function concept from CO4 — the agent selects the action (slot assignment) that maximises expected utility.

**Policy selection in rescheduling (`reschedule.py`):** When an interviewer becomes unavailable, the system follows a defined policy:
1. Release all affected assignments
2. Remove the unavailable interviewer from the search space
3. Re-run CSP only on displaced candidates (minimal disruption policy)
4. Return a structured diff of what changed vs. what remains unresolved

This bounded, targeted rescheduling reflects **bounded rationality** — solving the sub-problem efficiently rather than rerunning the entire schedule.

---

### CO5 · Reasoning Under Uncertainty
**File:** `scheduler/heuristics.py` → `ConfidenceEvaluator`, `FairnessChecker`

Each candidate carries a **confidence score per slot** (0.0 to 1.0), representing the probability that the candidate will be available and comfortable in that slot. This is used during scheduling to prefer high-confidence assignments:

```python
# ConfidenceEvaluator — scores final assignment
average_confidence = sum(conf per candidate) / total_assigned
```

The **FairnessChecker** performs distributional reasoning — it checks whether any priority group (VIP/NORMAL/LOW) holds more than 60% of morning or afternoon slots, flagging fairness violations. This is uncertainty-aware decision making: the system doesn't just find *a* valid schedule, it evaluates the quality of that schedule across multiple dimensions.

---

### CO6 · Integrated AI Pipeline & Explainability
**Files:** `app.py`, all scheduler modules

IntervAI is a **complete integrated AI reasoning pipeline**, combining all components from CO1–CO5 in a single `/api/schedule` call:

```
Input Data (candidates, interviewers, slots)
        ↓
Problem Formulation (state, actions, constraints)   ← CO1
        ↓
CSP Solver with MRV + LCV Heuristics               ← CO2, CO3
        ↓
Utility-Based Assignment                            ← CO4
        ↓
Confidence Scoring + Fairness Check                 ← CO5
        ↓
Explainable Output (assignment + violations + scores) ← CO6
```

The API response includes:
- Full assignment (who gets which slot with which interviewer)
- Fairness report with specific violations if any
- Per-candidate confidence scores
- Preferred slot annotations by priority group

**Ethics & Bias awareness (CO6):** The fairness checker directly addresses bias in heuristics — it detects when one priority group monopolises time slots, which would be unfair to lower-priority candidates. This is explicitly noted in the evaluation output.

---

## Project Structure

```
intervai/
├── app.py                  # Flask API — routes and pipeline orchestration
├── database.py             # SQLite persistence layer
├── requirements.txt
├── scheduler/
│   ├── models.py           # State representation (Candidate, Interviewer, TimeSlot)
│   ├── csp.py              # CSP engine — backtracking + MRV + LCV
│   ├── heuristics.py       # FairnessChecker, ConfidenceEvaluator, SlotAnnotator
│   └── reschedule.py       # Dynamic rescheduling engine
└── templates/
    └── index.html          # Web UI
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/state` | Fetch all candidates, interviewers, slots |
| POST | `/api/candidates` | Add a candidate |
| POST | `/api/interviewers` | Add an interviewer |
| POST | `/api/slots` | Add a time slot |
| POST | `/api/schedule` | Run the CSP scheduler |
| POST | `/api/reschedule/candidate/<id>` | Handle candidate cancellation |
| POST | `/api/reschedule/interviewer/<id>` | Handle interviewer unavailability |
| POST | `/api/reset` | Clear all assignments |

---

## Key AI Concepts Demonstrated

| Concept | Location | Course Outcome |
|---|---|---|
| PEAS / Problem Formulation | `models.py`, `app.py` | CO1 |
| State-space representation | `models.py` | CO1 |
| Heuristic-guided search | `csp.py → _build_domain()` | CO2 |
| CSP backtracking | `csp.py → _backtrack()` | CO3 |
| MRV heuristic | `csp.py → _order_candidates()` | CO3 |
| LCV heuristic (confidence-weighted) | `csp.py → _build_domain()` | CO3 |
| Constraint propagation | `csp.py → _is_consistent()` | CO3 |
| Utility-based decision making | `heuristics.py → ConfidenceEvaluator` | CO4 |
| Bounded rationality | `reschedule.py` | CO4 |
| Reasoning under uncertainty | `heuristics.py → confidence scores` | CO5 |
| Fairness / bias detection | `heuristics.py → FairnessChecker` | CO6 |
| Explainable AI output | API response structure | CO6 |

---

## References

- S. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed. — CH3 (Search), CH6 (CSP), CH16 (Utility)
- D. Poole and A. Mackworth, *Artificial Intelligence: Foundations of Computational Agents*, 2nd ed.

