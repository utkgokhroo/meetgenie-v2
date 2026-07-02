from __future__ import annotations

import os
from dotenv import load_dotenv
import yagmail

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

_SECTIONS = [
    ("Overview",            "overview",           False),
    ("Discussion Points",   "discussion_points",  True),
    ("Action Items",        "action_items",       True),
    ("Decisions",           "decisions",          True),
    ("Task Assignments",    "task_assignments",   True),
    ("Next Steps",          "next_steps",         True),
    ("Risks & Blockers",    "risks",              True),
    ("Open Questions",      "questions",          True),
    ("Follow Ups",          "follow_ups",         True),
]


def _format_field(value: object, is_list: bool) -> str:
    if is_list:
        items = value if isinstance(value, list) else []
        return "\n".join(f"  - {item}" for item in items) if items else "  None recorded"
    return str(value or "").strip() or "None recorded"


def send_summary_email(receiver_email: str, summary: dict) -> None:
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise ValueError(
            "Email credentials not configured. "
            "Set EMAIL_ADDRESS and EMAIL_PASSWORD in your .env file. "
            "For Gmail use an App Password: https://myaccount.google.com/apppasswords"
        )

    lines = ["MEETING SUMMARY", "=" * 40, ""]
    for heading, key, is_list in _SECTIONS:
        lines.append(f"{heading}:")
        lines.append(_format_field(summary.get(key, [] if is_list else ""), is_list))
        lines.append("")

    body = "\n".join(lines)

    yag = yagmail.SMTP(EMAIL_ADDRESS, EMAIL_PASSWORD)
    yag.send(to=receiver_email, subject="Meeting Summary", contents=body)
