from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Tuple

DB_NAME = "meetings.db"


@contextmanager
def _get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_NAME)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                filename       TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                overview       TEXT,
                language       TEXT,
                duration       REAL,
                transcript     TEXT,
                transcript_json TEXT,
                summary_json   TEXT
            )
        """)


def save_meeting(filename: str, result: Dict[str, Any]) -> None:
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO meetings
               (filename, overview, language, duration,
                transcript, transcript_json, summary_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                filename,
                result.get("overview", ""),
                result.get("language", ""),
                result.get("duration", 0),
                result.get("transcript", ""),
                json.dumps(result.get("segments", [])),
                json.dumps(result),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )


def delete_meeting(meeting_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))


def get_all_meetings() -> List[Tuple]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT id, filename, created_at, overview, summary_json "
            "FROM meetings ORDER BY created_at DESC"
        ).fetchall()


def search_meetings(keyword: str) -> List[Tuple]:
    q = f"%{keyword}%"
    with _get_conn() as conn:
        return conn.execute(
            """SELECT id, filename, created_at, overview, summary_json
               FROM meetings
               WHERE filename LIKE ? OR overview LIKE ? OR summary_json LIKE ?
               ORDER BY created_at DESC""",
            (q, q, q),
        ).fetchall()


if __name__ == "__main__":
    init_db()
    print("Database initialized")
