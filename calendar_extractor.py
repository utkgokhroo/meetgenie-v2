import json
from datetime import datetime

from services.gemini_client import get_client

MODEL_NAME = "gemini-2.5-flash"


def extract_calendar_events(transcript: str):
    client = get_client()

    today = datetime.today().strftime("%Y-%m-%d")

    prompt = f"""
You are an AI assistant that extracts calendar events from meeting transcripts.

Today's date is {today}.

Extract ONLY confirmed meetings.

For each event extract:

- title
- date (YYYY-MM-DD)
- time (24-hour HH:MM)
- duration_minutes
- description

Rules:

1. If time is missing, use 10:00.

2. If duration is missing, use 60.

3. Ignore cancelled meetings.

4. Ignore brainstorming.

5. Ignore vague ideas.

Return ONLY valid JSON.

Example:

[
    {{
        "title":"Demo",
        "date":"2026-07-15",
        "time":"10:00",
        "duration_minutes":60,
        "description":"Project demo"
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

    # Remove markdown if Gemini returns ```json
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "").strip()

    return json.loads(text)