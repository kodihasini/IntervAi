"""
database.py — SQLite persistence for IntervAI
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "intervai.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS interviewers (
        interviewer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        domains TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS slots (
        slot_id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        status TEXT DEFAULT 'available',
        assigned_candidate TEXT,
        assigned_interviewer TEXT
    );

    CREATE TABLE IF NOT EXISTS interviewer_slots (
        interviewer_id TEXT,
        slot_id TEXT,
        PRIMARY KEY (interviewer_id, slot_id)
    );

    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        priority TEXT NOT NULL,
        required_domain TEXT NOT NULL,
        preferred_duration INTEGER NOT NULL,
        assigned_slot TEXT,
        assigned_interviewer TEXT
    );

    CREATE TABLE IF NOT EXISTS candidate_slots (
        candidate_id TEXT,
        slot_id TEXT,
        confidence REAL DEFAULT 0.8,
        PRIMARY KEY (candidate_id, slot_id)
    );
    """)

    conn.commit()
    conn.close()


# ── Interviewers ──────────────────────────────────────────────────────────────

def add_interviewer(interviewer_id, name, domains, slot_ids):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO interviewers VALUES (?,?,?)",
              (interviewer_id, name, ",".join(domains)))
    c.execute("DELETE FROM interviewer_slots WHERE interviewer_id=?", (interviewer_id,))
    for sid in slot_ids:
        c.execute("INSERT OR IGNORE INTO interviewer_slots VALUES (?,?)", (interviewer_id, sid))
    conn.commit()
    conn.close()


def get_all_interviewers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM interviewers").fetchall()
    result = []
    for row in rows:
        slots = [r["slot_id"] for r in conn.execute(
            "SELECT slot_id FROM interviewer_slots WHERE interviewer_id=?", (row["interviewer_id"],)
        ).fetchall()]
        result.append({
            "interviewer_id": row["interviewer_id"],
            "name": row["name"],
            "domains": row["domains"].split(","),
            "available_slots": slots
        })
    conn.close()
    return result


def delete_interviewer(interviewer_id):
    conn = get_conn()
    conn.execute("DELETE FROM interviewers WHERE interviewer_id=?", (interviewer_id,))
    conn.execute("DELETE FROM interviewer_slots WHERE interviewer_id=?", (interviewer_id,))
    conn.commit()
    conn.close()


# ── Slots ─────────────────────────────────────────────────────────────────────

def add_slot(slot_id, date, start_time, end_time, duration_minutes):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO slots (slot_id,date,start_time,end_time,duration_minutes) VALUES (?,?,?,?,?)",
                 (slot_id, date, start_time, end_time, duration_minutes))
    conn.commit()
    conn.close()


def get_all_slots():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM slots").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_slot_status(slot_id, status, assigned_candidate=None, assigned_interviewer=None):
    conn = get_conn()
    conn.execute("UPDATE slots SET status=?, assigned_candidate=?, assigned_interviewer=? WHERE slot_id=?",
                 (status, assigned_candidate, assigned_interviewer, slot_id))
    conn.commit()
    conn.close()


def reset_all_slots():
    conn = get_conn()
    conn.execute("UPDATE slots SET status='available', assigned_candidate=NULL, assigned_interviewer=NULL")
    conn.commit()
    conn.close()


def delete_slot(slot_id):
    conn = get_conn()
    conn.execute("DELETE FROM slots WHERE slot_id=?", (slot_id,))
    conn.execute("DELETE FROM interviewer_slots WHERE slot_id=?", (slot_id,))
    conn.execute("DELETE FROM candidate_slots WHERE slot_id=?", (slot_id,))
    conn.commit()
    conn.close()


# ── Candidates ────────────────────────────────────────────────────────────────

def add_candidate(candidate_id, name, priority, required_domain, preferred_duration, slot_confidences):
    """slot_confidences: dict of slot_id -> confidence float"""
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO candidates (candidate_id,name,priority,required_domain,preferred_duration) VALUES (?,?,?,?,?)",
                 (candidate_id, name, priority, required_domain, preferred_duration))
    conn.execute("DELETE FROM candidate_slots WHERE candidate_id=?", (candidate_id,))
    for sid, conf in slot_confidences.items():
        conn.execute("INSERT INTO candidate_slots VALUES (?,?,?)", (candidate_id, sid, conf))
    conn.commit()
    conn.close()


def get_all_candidates():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM candidates").fetchall()
    result = []
    for row in rows:
        slot_rows = conn.execute(
            "SELECT slot_id, confidence FROM candidate_slots WHERE candidate_id=?",
            (row["candidate_id"],)
        ).fetchall()
        result.append({
            "candidate_id": row["candidate_id"],
            "name": row["name"],
            "priority": row["priority"],
            "required_domain": row["required_domain"],
            "preferred_duration": row["preferred_duration"],
            "assigned_slot": row["assigned_slot"],
            "assigned_interviewer": row["assigned_interviewer"],
            "available_slots": [r["slot_id"] for r in slot_rows],
            "confidence_scores": {r["slot_id"]: r["confidence"] for r in slot_rows}
        })
    conn.close()
    return result


def update_candidate_assignment(candidate_id, assigned_slot, assigned_interviewer):
    conn = get_conn()
    conn.execute("UPDATE candidates SET assigned_slot=?, assigned_interviewer=? WHERE candidate_id=?",
                 (assigned_slot, assigned_interviewer, candidate_id))
    conn.commit()
    conn.close()


def reset_all_assignments():
    conn = get_conn()
    conn.execute("UPDATE candidates SET assigned_slot=NULL, assigned_interviewer=NULL")
    conn.commit()
    conn.close()


def delete_candidate(candidate_id):
    conn = get_conn()
    conn.execute("DELETE FROM candidates WHERE candidate_id=?", (candidate_id,))
    conn.execute("DELETE FROM candidate_slots WHERE candidate_id=?", (candidate_id,))
    conn.commit()
    conn.close()
