from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

DB_NAME = "meetings.db"


@contextmanager
def _get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _get_conn() as conn:
        # -------------------------
        # Meetings table
        # -------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                filename        TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                overview        TEXT,
                language        TEXT,
                duration        REAL,
                transcript      TEXT,
                transcript_json TEXT,
                summary_json    TEXT
            )
        """)

        # -------------------------
        # Google users table
        # -------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                credentials TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_meeting(filename: str, result: Dict[str, Any]) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO meetings
            (
                filename,
                overview,
                language,
                duration,
                transcript,
                transcript_json,
                summary_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
        conn.execute(
            "DELETE FROM meetings WHERE id = ?",
            (meeting_id,),
        )


def get_all_meetings() -> List[Tuple]:
    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT
                id,
                filename,
                created_at,
                overview,
                summary_json
            FROM meetings
            ORDER BY created_at DESC
            """
        ).fetchall()


def search_meetings(keyword: str) -> List[Tuple]:
    q = f"%{keyword}%"

    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT
                id,
                filename,
                created_at,
                overview,
                summary_json
            FROM meetings
            WHERE
                filename LIKE ?
                OR overview LIKE ?
                OR summary_json LIKE ?
            ORDER BY created_at DESC
            """,
            (q, q, q),
        ).fetchall()


# ==========================================================
# GOOGLE USER FUNCTIONS
# ==========================================================

def save_user(email: str, name: str, credentials: str) -> None:
    """
    Save or update a Google user.
    credentials should be creds.to_json()
    """
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO users
            (email, name, credentials)
            VALUES (?, ?, ?)
            """,
            (
                email,
                name,
                credentials,
            ),
        )


def get_user(email: str) -> Optional[Tuple]:
    """
    Returns:
    (email, name, credentials)
    or None
    """
    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT
                email,
                name,
                credentials
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()


def update_user_credentials(email: str, credentials: str) -> None:
    """
    Update credentials after token refresh.
    """
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE users
            SET credentials = ?
            WHERE email = ?
            """,
            (
                credentials,
                email,
            ),
        )


def delete_user(email: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            DELETE FROM users
            WHERE email = ?
            """,
            (email,),
        )


def get_all_users() -> List[Tuple]:
    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT
                email,
                name,
                created_at
            FROM users
            ORDER BY created_at DESC
            """
        ).fetchall()


if __name__ == "__main__":
    init_db()
    print("Database initialized")