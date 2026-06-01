"""
IntervAI - Flask Application (SQLite version)
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request, render_template
from database import (
    init_db, get_all_candidates, get_all_interviewers, get_all_slots,
    add_candidate, add_interviewer, add_slot,
    delete_candidate, delete_interviewer, delete_slot,
    update_slot_status, update_candidate_assignment,
    reset_all_slots, reset_all_assignments
)
from scheduler import (
    CSPScheduler, FairnessChecker, ConfidenceEvaluator,
    annotate_preferred_slots, ReschedulingEngine,
    Candidate, Interviewer, TimeSlot, Priority, SlotStatus
)

app = Flask(__name__)
init_db()


# ── Helpers: DB rows → model objects ─────────────────────────────────────────

def load_models():
    cand_rows = get_all_candidates()
    iw_rows   = get_all_interviewers()
    slot_rows = get_all_slots()

    candidates  = [Candidate(
        c["candidate_id"], c["name"], Priority[c["priority"]],
        c["required_domain"], c["available_slots"],
        c["confidence_scores"], c["preferred_duration"],
        c.get("assigned_slot"), c.get("assigned_interviewer")
    ) for c in cand_rows]

    interviewers = [Interviewer(
        i["interviewer_id"], i["name"], i["domains"], i["available_slots"]
    ) for i in iw_rows]

    slots = [TimeSlot(
        s["slot_id"], s["start_time"], s["end_time"], s["date"],
        s["duration_minutes"],
        SlotStatus(s["status"]),
        s.get("assigned_candidate"), s.get("assigned_interviewer")
    ) for s in slot_rows]

    return candidates, interviewers, slots


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── State ─────────────────────────────────────────────────────────────────────

@app.route("/api/state")
def get_state():
    candidates, interviewers, slots = load_models()
    return jsonify({
        "candidates":  [c.to_dict() for c in candidates],
        "interviewers":[i.to_dict() for i in interviewers],
        "slots":       [s.to_dict() for s in slots],
    })


# ── Slots CRUD ────────────────────────────────────────────────────────────────

@app.route("/api/slots", methods=["POST"])
def create_slot():
    d = request.json
    slot_id = "S" + uuid.uuid4().hex[:6].upper()
    add_slot(slot_id, d["date"], d["start_time"], d["end_time"], int(d["duration_minutes"]))
    return jsonify({"success": True, "slot_id": slot_id})

@app.route("/api/slots/<slot_id>", methods=["DELETE"])
def remove_slot(slot_id):
    delete_slot(slot_id)
    return jsonify({"success": True})


# ── Interviewers CRUD ─────────────────────────────────────────────────────────

@app.route("/api/interviewers", methods=["POST"])
def create_interviewer():
    d = request.json
    iw_id = "I" + uuid.uuid4().hex[:6].upper()
    domains = [x.strip() for x in d["domains"].split(",")]
    slot_ids = d.get("slot_ids", [])
    add_interviewer(iw_id, d["name"], domains, slot_ids)
    return jsonify({"success": True, "interviewer_id": iw_id})

@app.route("/api/interviewers/<iw_id>", methods=["DELETE"])
def remove_interviewer(iw_id):
    delete_interviewer(iw_id)
    return jsonify({"success": True})


# ── Candidates CRUD ───────────────────────────────────────────────────────────

@app.route("/api/candidates", methods=["POST"])
def create_candidate():
    d = request.json
    cid = "C" + uuid.uuid4().hex[:6].upper()
    slot_ids    = d.get("slot_ids", [])
    confidences = d.get("confidence_scores", {})
    # Default confidence 0.8 for any slot not explicitly scored
    slot_conf = {sid: float(confidences.get(sid, 0.8)) for sid in slot_ids}
    add_candidate(cid, d["name"], d["priority"], d["required_domain"],
                  int(d["preferred_duration"]), slot_conf)
    return jsonify({"success": True, "candidate_id": cid})

@app.route("/api/candidates/<cid>", methods=["DELETE"])
def remove_candidate(cid):
    delete_candidate(cid)
    return jsonify({"success": True})


# ── Scheduler ─────────────────────────────────────────────────────────────────

@app.route("/api/schedule", methods=["POST"])
def run_schedule():
    # Reset previous assignments
    reset_all_assignments()
    reset_all_slots()

    candidates, interviewers, slots = load_models()

    if not candidates:
        return jsonify({"success": False, "message": "No candidates added yet."})
    if not interviewers:
        return jsonify({"success": False, "message": "No interviewers added yet."})
    if not slots:
        return jsonify({"success": False, "message": "No slots added yet."})

    solver = CSPScheduler(candidates=candidates, interviewers=interviewers, slots=slots)
    assignment = solver.solve()

    if assignment is None:
        return jsonify({"success": False, "message": "No valid schedule found. Check that slots, domains, and durations are compatible."})

    solver.apply_assignment(assignment)

    # Persist assignments
    for cid, (sid, iid) in assignment.items():
        update_candidate_assignment(cid, sid, iid)
        update_slot_status(sid, "booked", cid, iid)

    candidates, interviewers, slots = load_models()
    cand_map = {c.candidate_id: c for c in candidates}
    slot_map = {s.slot_id: s for s in slots}

    fairness   = FairnessChecker().check(assignment, cand_map, slot_map)
    confidence = ConfidenceEvaluator().score(assignment, cand_map)
    preferred  = annotate_preferred_slots(slots, candidates)

    return jsonify({
        "success": True,
        "assignment": {cid: {"slot": sid, "interviewer": iid} for cid, (sid, iid) in assignment.items()},
        "fairness":   fairness,
        "confidence": confidence,
        "preferred_slots": preferred,
        "candidates": [c.to_dict() for c in candidates],
        "slots":      [s.to_dict() for s in slots],
    })


# ── Reschedule ────────────────────────────────────────────────────────────────

@app.route("/api/reschedule/candidate/<candidate_id>", methods=["POST"])
def cancel_candidate(candidate_id):
    candidates, interviewers, slots = load_models()
    cand_map = {c.candidate_id: c for c in candidates}
    iw_map   = {i.interviewer_id: i for i in interviewers}
    slot_map = {s.slot_id: s for s in slots}

    engine = ReschedulingEngine(cand_map, iw_map, slot_map)
    result = engine.handle_candidate_cancellation(candidate_id)

    if result["success"] and result.get("freed_slot"):
        update_slot_status(result["freed_slot"], "available", None, None)
        update_candidate_assignment(candidate_id, None, None)

    candidates2, _, slots2 = load_models()
    result["candidates"] = [c.to_dict() for c in candidates2]
    result["slots"]      = [s.to_dict() for s in slots2]
    return jsonify(result)


@app.route("/api/reschedule/interviewer/<interviewer_id>", methods=["POST"])
def interviewer_unavailable(interviewer_id):
    candidates, interviewers, slots = load_models()
    cand_map = {c.candidate_id: c for c in candidates}
    iw_map   = {i.interviewer_id: i for i in interviewers}
    slot_map = {s.slot_id: s for s in slots}

    engine = ReschedulingEngine(cand_map, iw_map, slot_map)
    result = engine.handle_interviewer_unavailable(interviewer_id)

    # Persist freed slots
    for c in cand_map.values():
        if c.assigned_interviewer is None and c.assigned_slot is None:
            # was displaced
            pass

    # Persist new assignments from rescheduling
    for change in result.get("changes", []):
        update_candidate_assignment(change["candidate"], change["new_slot"], change["new_interviewer"])
        update_slot_status(change["new_slot"], "booked", change["candidate"], change["new_interviewer"])

    # Mark interviewer's previously booked slots as available if unresolved
    for cid in result.get("unresolved", []):
        cand = cand_map.get(cid)
        if cand and cand.assigned_slot:
            update_slot_status(cand.assigned_slot, "available", None, None)
            update_candidate_assignment(cid, None, None)

    candidates2, _, slots2 = load_models()
    result["candidates"] = [c.to_dict() for c in candidates2]
    result["slots"]      = [s.to_dict() for s in slots2]
    return jsonify(result)


@app.route("/api/reset", methods=["POST"])
def reset_schedule():
    reset_all_assignments()
    reset_all_slots()
    return jsonify({"success": True, "message": "Assignments cleared. Data preserved."})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
