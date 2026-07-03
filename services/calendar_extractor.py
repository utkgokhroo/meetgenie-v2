import json
from services.gemini_client import get_client, MODEL_NAME


def extract_calendar_events(transcript: str):
    """
    Extract calendar events from a meeting transcript using Gemini.

    Returns:
        list[dict]
    """

    client = get_client()

    prompt = f"""
You are an AI assistant that extracts calendar events from meeting transcripts.

Return ONLY valid JSON.

Extract every event mentioned in the transcript.

Each event must contain:

- title
- date (YYYY-MM-DD)
- time (HH:MM in 24-hour format)
- duration_minutes
- description
- reminder_minutes

Rules:

1. If time is not mentioned, use "10:00".
2. If duration is not mentioned, use 60.
3. If reminder is not mentioned, use 30.
4. If the date, moth or year is missing, assume the current date, month or year.
5. Return ONLY a JSON array.
6. Do not wrap the JSON inside markdown.

Example:

[
  {{
    "title": "Client Demo",
    "date": "2026-07-15",
    "time": "15:00",
    "duration_minutes": 60,
    "description": "Demo with ABC client",
    "reminder_minutes": 30
  }}
]

Transcript:

{transcript}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    text = response.text.strip()

    # Remove markdown if Gemini adds it
    if text.startswith("```json"):
        text = text.replace("```json", "").replace("```", "").strip()

    elif text.startswith("```"):
        text = text.replace("```", "").strip()

    try:
        events = json.loads(text)

        if not isinstance(events, list):
            return []

        return events

    except Exception as e:
        print(f"Calendar extraction error: {e}")
        print(text)
        return []