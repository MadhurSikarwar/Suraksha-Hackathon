import sqlite3
import json
import os
import logging
import threading
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Use environment variable for DB path (deployment-safe)
DB_PATH = os.environ.get("AUDIT_DB_PATH", "audit_logs.db")

# Thread lock for SQLite write safety (SQLite allows concurrent reads but not writes)
_db_lock = threading.Lock()


@contextmanager
def _get_conn():
    """Context manager that always closes the connection, even on exception."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Creates the audit table if it doesn't exist. Safe to call multiple times."""
    with _get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS case_logs (
                task_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                decision TEXT NOT NULL,
                fraud_score REAL NOT NULL,
                extracted_entities TEXT,
                reasons TEXT,
                officer_override TEXT
            )
        ''')
    logger.info(f"Audit DB initialized at {DB_PATH}")


def log_case(task_id: str, decision: str, fraud_score: float,
             extracted_entities: dict, reasons: list):
    """
    Inserts or replaces a case log entry.
    Thread-safe via lock to prevent write conflicts on concurrent requests.
    """
    try:
        with _db_lock, _get_conn() as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO case_logs
                   (task_id, timestamp, decision, fraud_score, extracted_entities, reasons, officer_override)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (
                    str(task_id),
                    datetime.utcnow().isoformat() + "Z",
                    str(decision),
                    float(fraud_score),
                    json.dumps(extracted_entities or {}),
                    json.dumps(reasons or []),
                    None
                )
            )
    except Exception as e:
        logger.error(f"Audit log write failed for task {task_id}: {e}")


def override_case(task_id: str, new_decision: str, reason: str) -> bool:
    """
    Updates a case with an officer override decision.
    Returns True if a row was updated, False if task_id not found.
    """
    try:
        override_data = json.dumps({
            "new_decision": new_decision,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        with _db_lock, _get_conn() as conn:
            cursor = conn.execute(
                'UPDATE case_logs SET officer_override = ?, decision = ? WHERE task_id = ?',
                (override_data, new_decision, str(task_id))
            )
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Override failed for task {task_id}: {e}")
        return False


def get_all_cases(limit: int = 200) -> list:
    """
    Returns up to `limit` most recent cases from the audit log.
    Capped to prevent memory issues on large deployments.
    """
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                'SELECT * FROM case_logs ORDER BY timestamp DESC LIMIT ?',
                (limit,)
            ).fetchall()
        return [
            {
                "task_id": row["task_id"],
                "timestamp": row["timestamp"],
                "decision": row["decision"],
                "fraud_score": row["fraud_score"],
                "extracted_entities": json.loads(row["extracted_entities"] or "{}"),
                "reasons": json.loads(row["reasons"] or "[]"),
                "officer_override": json.loads(row["officer_override"]) if row["officer_override"] else None
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Failed to fetch audit cases: {e}")
        return []
