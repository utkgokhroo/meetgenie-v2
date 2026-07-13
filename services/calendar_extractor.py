import json
import re
import time

from services.gemini_client import get_client, MODEL_NAME


def _generate_with_retry(prompt: str, retries: int = 3):

    last_exc = None

    for attempt in range(retries):

        try:

            response = get_client().models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )

            print(
                f"[calendar] Gemini responded (attempt {attempt + 1})"
            )

            return response

        except Exception as exc:

            last_exc = exc
            err = str(exc)

            print(
                f"[calendar] Attempt {attempt + 1} failed: "
                f"{err[:150]}"
            )

            if (
                "503" in err
                or "UNAVAILABLE" in err
                or "429" in err
            ):

                if attempt < retries - 1:

                    wait = 5 * (attempt + 1)

                    print(
                        f"[calendar] Retrying in {wait} seconds..."
                    )

                    time.sleep(wait)

                    continue

            raise

    raise last_exc


def extract_calendar_events(transcript: str):

    prompt = f"""
You are an AI assistant that extracts calendar events from meeting transcripts.

Return ONLY valid JSON.

Extract ONLY future meetings, appointments, demos, interviews,
reviews, presentations, deadlines, or scheduled calls.

Ignore discussion topics and historical events.

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
4. If day/month/year is missing, infer it from the transcript or use the current date.
5. Return ONLY a JSON array.
6. Never wrap the JSON in markdown.
7. Return [] if no calendar events are found.

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

    try:

        response = _generate_with_retry(prompt)

        text = getattr(response, "text", "") or ""

        if not text:

            try:
                parts = response.candidates[0].content.parts

                text = "\n".join(
                    getattr(part, "text", "")
                    for part in parts
                    if not getattr(part, "thought", False)
                )

            except Exception:
                text = ""

        text = text.strip()

        text = (
            text.replace("```json", "")
                .replace("```", "")
                .strip()
        )

        match = re.search(
            r"\[.*\]",
            text,
            flags=re.DOTALL,
        )

        if match:
            text = match.group(0)

        events = json.loads(text)

        if not isinstance(events, list):

            print("[calendar] Response was not a list.")

            return []

        print(
            f"[calendar] Extracted {len(events)} event(s)."
        )

        return events

    except Exception as e:

        print(f"[calendar] Extraction failed: {e}")

        return []