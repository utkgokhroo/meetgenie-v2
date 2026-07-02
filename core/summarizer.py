from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional

from services.gemini_client import get_client, MODEL_NAME

EMPTY_SUMMARY: Dict[str, Any] = {
    "overview": "",
    "discussion_points": [],
    "action_items": [],
    "decisions": [],
    "task_assignments": [],
    "next_steps": [],
    "risks": [],
    "questions": [],
    "follow_ups": [],
}

_cache: Dict[str, Dict] = {}
_MAX_CHUNKS = 3
_MAX_WORDS_PER_CHUNK = 2500


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def split_transcript(text: str, max_words: int = _MAX_WORDS_PER_CHUNK) -> List[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[i : i + max_words])
        for i in range(0, len(words), max_words)
    ]


def _normalise_summary(parsed: Dict[str, Any]) -> Dict[str, Any]:
    summary = EMPTY_SUMMARY.copy()
    for key in summary:
        value = parsed.get(key, summary[key])
        if key == "overview":
            summary[key] = str(value or "").strip()
        elif isinstance(value, list):
            summary[key] = [str(item).strip() for item in value if str(item).strip()]
        elif value:
            summary[key] = [str(value).strip()]
    return summary


def _safe_json_parse(text: str) -> Optional[Dict]:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _response_text(response: Any) -> str:
    # Fast path: non-thinking models populate response.text directly.
    text = getattr(response, "text", "") or ""
    if text.strip():
        return text

    # Thinking model path
    try:
        parts = response.candidates[0].content.parts
        output_parts = [
            getattr(part, "text", "")
            for part in parts
            if not getattr(part, "thought", False)
        ]
        joined = "\n".join(t for t in output_parts if t)
        if joined.strip():
            return joined
    except Exception:
        pass

    return ""


def _generate_with_retry(prompt: str, retries: int = 3) -> Optional[Any]:
    last_exc = None
    for attempt in range(retries):
        try:
            response = get_client().models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            print(f"[summarizer] Gemini responded (attempt {attempt + 1})")
            return response
        except Exception as exc:
            last_exc = exc
            err = str(exc)
            print(f"[summarizer] Attempt {attempt + 1} failed: {err[:120]}")
            if "429" in err:
                return None
            wait = 5 * (attempt + 1)
            if attempt < retries - 1:
                time.sleep(wait)

    print(f"[summarizer] All {retries} attempts failed: {last_exc}")
    return None


def _summarize_chunks(chunks: List[str]) -> Dict[str, Any]:
    combined = "\n\n".join(
        f"PART {i + 1}:\n{chunk}" for i, chunk in enumerate(chunks)
    )

    prompt = (
        "You are a meeting intelligence engine. "
        "Your response must be ONLY a single valid JSON object. "
        "Do not include any text before or after the JSON. "
        "Do not use markdown fences. Do not explain anything.\n\n"
        "Return exactly this structure:\n"
        '{"overview":"","discussion_points":[],"action_items":[],'
        '"decisions":[],"task_assignments":[],"next_steps":[],'
        '"risks":[],"questions":[],"follow_ups":[]}\n\n'
        "Rules:\n"
        "- overview: 2-4 sentence summary of the meeting\n"
        "- discussion_points: list of key topics discussed\n"
        "- action_items: list of tasks assigned, include owner if named\n"
        "- decisions: list of decisions made\n"
        "- task_assignments: list of who is responsible for what\n"
        "- next_steps: list of planned next actions\n"
        "- risks: list of risks or blockers mentioned\n"
        "- questions: list of unanswered questions raised\n"
        "- follow_ups: list of items to follow up on\n"
        "- Use empty arrays [] for categories with no items\n\n"
        f"Meeting transcript:\n{combined}"
    )

    response = _generate_with_retry(prompt)
    if response:
        raw = _response_text(response)
        print(f"[summarizer] Raw response length: {len(raw)} chars")
        print(f"[summarizer] Raw response preview: {raw[:200].replace(chr(10), ' ')}")
        parsed = _safe_json_parse(raw)
        if parsed:
            print("[summarizer] JSON parsed successfully")
            return _normalise_summary(parsed)
        print(f"[summarizer] JSON parse FAILED. Full response: {raw[:500]}")

    raise RuntimeError("Gemini did not return a valid meeting summary.")


def generate_summary(transcript: str) -> Dict[str, Any]:
    if not transcript or not transcript.strip():
        return {
            **EMPTY_SUMMARY,
            "overview": (
                "Error: transcript was empty. "
                "Check that the uploaded file contains audio or text."
            ),
        }

    try:
        key = _cache_key(transcript)
        if key in _cache:
            cached = _cache[key]
            if cached.get("overview", "").startswith("Error:"):
                del _cache[key]
            else:
                print("[summarizer] Returning cached result")
                return cached

        chunks = split_transcript(transcript)[:_MAX_CHUNKS]
        print(f"[summarizer] Summarising {len(chunks)} chunk(s) from {len(transcript)} char transcript")
        result = _summarize_chunks(chunks)

        _cache[key] = result
        return result

    except Exception as exc:
        print(f"[summarizer] generate_summary failed: {exc}")
        return {**EMPTY_SUMMARY, "overview": f"Error: {exc}"}
