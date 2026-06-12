from google import genai
from dotenv import load_dotenv
import os
import json
import time
import hashlib

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.5-flash"

EMPTY_SUMMARY = {
    "overview": "",
    "discussion_points": [],
    "action_items": [],
    "decisions": [],
    "task_assignments": [],
    "next_steps": [],
    "risks": [],
    "questions": [],
    "follow_ups": []
}

cache = {}

def get_cache_key(text):
    return hashlib.md5(text.encode()).hexdigest()


def split_transcript(text, max_words=2500):
    words = text.split()
    if not words:
        return []
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def safe_json_parse(text):
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def generate_with_retry(prompt, retries=2):
    for attempt in range(retries):
        try:
            print(f"🚀 API call attempt {attempt+1}")
            return client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

        except Exception as e:
            error_str = str(e)
            print(f"[ERROR] {error_str}")

            if "429" in error_str:
                print("❌ Quota exceeded. Skipping retries.")
                return None

            if "503" in error_str:
                wait_time = 10
                print(f"⏳ Server busy. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                break

    return None

def summarize_chunk(chunks):
    combined_text = "\n\n".join(
        [f"PART {i+1}:\n{chunk}" for i, chunk in enumerate(chunks)]
    )

    prompt = f"""
    You are a meeting intelligence engine.

    Return ONLY valid JSON.

    {{
    "overview":"",
    "discussion_points":[],
    "action_items":[],
    "decisions":[],
    "task_assignments":[],
    "next_steps":[],
    "risks":[],
    "questions":[],
    "follow_ups":[]
    }}

    Rules:
    - Extract key discussion points
    - Extract decisions
    - Extract action items
    - Extract risks and blockers
    - Extract unanswered questions
    - Extract follow ups
    - Preserve names if mentioned
    - Return empty arrays if none exist

    Transcript:
    {combined_text}
    """

    response = generate_with_retry(prompt)

    if response:
        parsed = safe_json_parse(response.text)
        if parsed:
            return parsed

    return EMPTY_SUMMARY.copy()


def merge_summaries(summaries):
    merged = {key: [] for key in EMPTY_SUMMARY}
    merged["overview"] = ""
    for s in summaries:
        merged["overview"] += s.get("overview", "") + " "
        for key in [
        "discussion_points",
        "action_items",
        "decisions",
        "task_assignments",
        "next_steps",
        "risks",
        "questions",
        "follow_ups"
        ]:
            merged[key].extend(s.get(key, []))
    return merged


def refine_summary(merged):
    return merged


def generate_summary(transcript):
    if not transcript or not transcript.strip():
        return {
            **EMPTY_SUMMARY,
            "overview": "Error: transcript was empty. Check that the uploaded file contains audio or text."
        }

    try:
        key = get_cache_key(transcript)
        if key in cache:
            print("⚡ Using cached result")
            return cache[key]

        chunks = split_transcript(transcript)

        MAX_CHUNKS = 3
        chunks = chunks[:MAX_CHUNKS]

        summary = summarize_chunk(chunks)

        final = refine_summary(summary)

        cache[key] = final

        return final

    except Exception as e:
        return {**EMPTY_SUMMARY, "overview": f"Error: {str(e)}"}