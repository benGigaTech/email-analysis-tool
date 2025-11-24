import os
import sqlite3
from datetime import datetime
from threading import Lock
import json

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "quarantine.db")

_db_lock = Lock()


def init_db():
    """Create the SQLite database and table if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS quarantine_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                sender TEXT,
                subject TEXT,
                received_datetime TEXT,
                risk_score INTEGER,
                classification TEXT,
                reasons TEXT,
                moved INTEGER DEFAULT 0,
                created_at TEXT,
                released INTEGER DEFAULT 0,
                released_at TEXT,
                user_email TEXT
            )
            """
        )
        conn.commit()
        conn.close()


def log_quarantine_event(user_email: str, email: dict, score: dict, moved: bool):
    """Insert a record for a processed email (quarantined or not)."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        message_id = email["id"]
        sender = (
            (email.get("from", {}) or {})
            .get("emailAddress", {})
            .get("address")
        )
        subject = email.get("subject")
        received = email.get("receivedDateTime")
        risk_score = score.get("risk_score")
        classification = score.get("classification")
        reasons = json.dumps(score.get("reasons", []))
        created_at = datetime.utcnow().isoformat() + "Z"

        cur.execute(
            """
            INSERT INTO quarantine_events
                (message_id, sender, subject, received_datetime, risk_score,
                 classification, reasons, moved, created_at, released, user_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                message_id,
                sender,
                subject,
                received,
                risk_score,
                classification,
                reasons,
                int(moved),
                created_at,
                user_email,
            ),
        )

        conn.commit()
        conn.close()


def list_quarantine_events(limit: int = 100):
    """Return recent quarantine events as a list of dicts."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, message_id, sender, subject, received_datetime, risk_score,
                   classification, reasons, moved, created_at, released, released_at, user_email
            FROM quarantine_events
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()

    events = []
    for row in rows:
        events.append(
            {
                "id": row[0],
                "message_id": row[1],
                "sender": row[2],
                "subject": row[3],
                "received_datetime": row[4],
                "risk_score": row[5],
                "classification": row[6],
                "reasons": json.loads(row[7] or "[]"),
                "moved": bool(row[8]),
                "created_at": row[9],
                "released": bool(row[10]),
                "released_at": row[11],
                "user_email": row[12],
            }
        )
    return events


def get_event_by_id(event_id: int):
    """Fetch a single quarantine event by numeric ID."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, message_id, sender, subject, received_datetime, risk_score,
                   classification, reasons, moved, created_at, released, released_at, user_email
            FROM quarantine_events
            WHERE id = ?
            """,
            (event_id,),
        )
        row = cur.fetchone()
        conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "message_id": row[1],
        "sender": row[2],
        "subject": row[3],
        "received_datetime": row[4],
        "risk_score": row[5],
        "classification": row[6],
        "reasons": json.loads(row[7] or "[]"),
        "moved": bool(row[8]),
        "created_at": row[9],
        "released": bool(row[10]),
        "released_at": row[11],
        "user_email": row[12],
    }


def mark_released(event_id: int):
    """Mark an event as released in the DB."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        cur.execute(
            """
            UPDATE quarantine_events
            SET released = 1, released_at = ?
            WHERE id = ?
            """,
            (now, event_id),
        )
        conn.commit()
        conn.close()


def get_dashboard_stats():
    """
    Get simple statistics for the dashboard:
    - Total emails processed
    - Quarantined
    - Released
    """
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(moved) as quarantined,
                SUM(released) as released
            FROM quarantine_events
            """
        )
        row = cur.fetchone()
        conn.close()

    total = row[0] or 0
    quarantined = row[1] or 0
    released = row[2] or 0
    
    # Calculate "Allowed" (safe)
    allowed = total - quarantined

    return {
        "total": total,
        "quarantined": quarantined,
        "released": released,
        "allowed": allowed
    }
