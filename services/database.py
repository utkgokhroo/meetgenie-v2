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

        # -------------------------
        # Meetings table
        # -------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                filename        TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                overview        TEXT,
                language        TEXT,
                duration        REAL,
                transcript      TEXT,
                transcript_json TEXT,
                summary_json    TEXT,

                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # -------------------------
        # Persistent sessions table
        # Maps a random token → user email so we can restore sessions
        # on browser refresh without asking the user to log in again.
        # -------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                email      TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def save_meeting(user_id: int, filename: str, result: Dict[str, Any]) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO meetings
            (
                user_id,
                filename,
                overview,
                language,
                duration,
                transcript,
                transcript_json,
                summary_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
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


def delete_meeting(meeting_id: int, user_id: int) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            DELETE FROM meetings
            WHERE id = ?
            AND user_id = ?
            """,
            (meeting_id, user_id),
        )

def get_all_meetings(user_id: int) -> List[Tuple]:
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
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()


def search_meetings(user_id: int, keyword: str) -> List[Tuple]:
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
            WHERE user_id = ?
            AND (
                filename LIKE ?
                OR overview LIKE ?
                OR summary_json LIKE ?
            )
            ORDER BY created_at DESC
            """,
            (user_id, q, q, q),
        ).fetchall()

# ==========================================================
# GOOGLE USER FUNCTIONS
# ==========================================================

def save_user(email: str, name: str, credentials: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (email, name, credentials)
            VALUES (?, ?, ?)
            ON CONFLICT(email)
            DO UPDATE SET
                name = excluded.name,
                credentials = excluded.credentials
            """,
            (
                email,
                name,
                credentials,
            ),
        )


def get_user(email: str) -> Optional[Tuple]:
    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT
                id,
                email,
                name,
                credentials,
                created_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

def count_user_meetings(user_id: int) -> int:
    with _get_conn() as conn:
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM meetings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        return result[0]

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


def get_dashboard_stats(user_id: int) -> Dict[str, Any]:
    """Return meeting count and total hours processed for the dashboard."""
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) as meeting_count,
                COALESCE(SUM(duration), 0) as total_seconds
            FROM meetings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return {
            "meeting_count": row[0] if row else 0,
            "hours_processed": round((row[1] if row else 0) / 3600, 1),
        }


def get_recent_meetings(user_id: int, limit: int = 5) -> List[Tuple]:
    """Return the most recent N meetings for the dashboard."""
    with _get_conn() as conn:
        return conn.execute(
            """
            SELECT id, filename, created_at, overview, summary_json
            FROM meetings
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()


# ==========================================================
# SESSION FUNCTIONS
# ==========================================================

def create_session(token: str, email: str) -> None:
    """Persist a session token → email mapping."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (token, email) VALUES (?, ?)",
            (token, email),
        )


def get_session(token: str) -> Optional[str]:
    """Return the email for a session token, or None if not found."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT email FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
        return row[0] if row else None


def delete_session(token: str) -> None:
    """Remove a session token (called on sign-out)."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


if __name__ == "__main__":
    init_db()
    print("Database initialized")