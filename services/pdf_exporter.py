from __future__ import annotations
from fpdf import FPDF

SECTIONS = [
    ("Key Discussion Points", "discussion_points"),
    ("Action Items",          "action_items"),
    ("Decisions",             "decisions"),
    ("Task Assignments",      "task_assignments"),
    ("Next Steps",            "next_steps"),
    ("Risks & Blockers",      "risks"),
    ("Open Questions",        "questions"),
    ("Follow Ups",            "follow_ups"),
]


def _safe(text: object) -> str:
    """Sanitise text for Latin-1 PDF output."""
    return (
        str(text or "")
        .replace("•", "-")
        .replace("—", "-")
        .replace("–", "-")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def _add_wrapped_text(pdf: FPDF, text: str, size: int = 11, bold: bool = False) -> None:
    pdf.set_font("Helvetica", style="B" if bold else "", size=size)
    pdf.multi_cell(0, 6, _safe(text).replace("\n", " ").replace("\r", ""))


def _add_bullet_list(pdf: FPDF, items: list) -> None:
    pdf.set_font("Helvetica", size=11)
    if not items:
        pdf.multi_cell(0, 6, "None recorded")
        return
    for item in items:
        if not item:
            continue
        pdf.multi_cell(0, 6, f"- {_safe(item).replace(chr(13), '')}")
        pdf.ln(1)


def generate_summary_pdf(result: dict, title: str = "Meeting Summary") -> bytes:
    pdf = FPDF()
    pdf.set_margins(left=10, top=10, right=10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Overview
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 8, "Meeting Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    _add_wrapped_text(pdf, result.get("overview", "").strip() or "None recorded")
    pdf.ln(4)

    # All summary sections
    for heading, key in SECTIONS:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        _add_bullet_list(pdf, result.get(key, []))
        pdf.ln(4)

    return bytes(pdf.output(dest="S"))
