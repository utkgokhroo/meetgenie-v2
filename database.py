import sqlite3
import json
from datetime import datetime

DB_NAME = "meetings.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            overview TEXT,

            language TEXT,
            duration REAL,

            transcript TEXT,
            transcript_json TEXT,

            summary_json TEXT
        )
        """)
    conn.commit()
    conn.close()


def save_meeting(filename, result):

    conn = sqlite3.connect(DB_NAME)

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
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()

def delete_meeting(meeting_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()


def get_all_meetings():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute(
        "SELECT id, filename, created_at, overview, summary_json FROM meetings ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def search_meetings(keyword):
    conn = sqlite3.connect(DB_NAME)
    q = f"%{keyword}%"
    cursor = conn.execute(
        """SELECT id, filename, created_at, overview, summary_json FROM meetings
           WHERE filename LIKE ? OR overview LIKE ? OR summary_json LIKE ?
           ORDER BY created_at DESC""",
        (q, q, q)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    print("Database initialized")
