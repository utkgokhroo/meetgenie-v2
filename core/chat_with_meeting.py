"""
Chat / Q&A over a meeting transcript via Gemini.
"""

from __future__ import annotations

from services.gemini_client import get_client, MODEL_NAME


def ask_meeting_question(meeting_context: str, question: str) -> str:
    prompt = f"""
You are MeetGenie, an intelligent AI Meeting Copilot.

You have access to meeting information including:
- transcript
- speaker information
- speaker count
- top speaker
- participation statistics
- talk time
- speaker sentiment

Your job is to answer ANY question related to the meeting.

You may:
- summarize discussions
- explain what a speaker meant
- elaborate on ideas discussed in the meeting
- identify action items and decisions
- provide recommendations and next steps
- answer follow-up questions
- count speakers
- identify who said what
- determine who spoke the most
- explain a specific speaker's statements
- make simple inferences that are clearly supported by the meeting data

Be helpful, conversational, and concise.

If the information truly cannot be determined from the meeting data, say:

"I could not determine that from the meeting data."

Meeting Data:
{meeting_context}

User Question:
{question}
"""

    response = get_client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    return response.text