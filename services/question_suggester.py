from services.gemini_client import get_client, MODEL_NAME


def generate_questions(meeting_context):
    prompt = f"""
Generate 5 useful questions a user might ask about this meeting.

Requirements:
- Questions must be specific to this meeting.
- Keep them short.
- Return ONLY the questions, one per line.

Meeting:
{meeting_context}
"""

    response = get_client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    questions = [
        q.strip("-• ").strip()
        for q in response.text.split("\n")
        if q.strip()
    ]

    return questions[:5]