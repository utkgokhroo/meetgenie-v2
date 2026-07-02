"""
Chat / Q&A over a meeting transcript via Gemini.

Fix: previously created its own genai.Client with its own load_dotenv()
call. Now uses the shared gemini_client module.
"""

from __future__ import annotations

from services.gemini_client import get_client, MODEL_NAME


def ask_meeting_question(transcript: str, question: str) -> str:
    prompt = f"""You are a meeting assistant.

Use ONLY the meeting transcript below to answer the question.
If the answer is not in the transcript, say:
"I could not find that information in the meeting transcript."

Meeting Transcript:
{transcript}

Question:
{question}"""

    response = get_client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return response.text
