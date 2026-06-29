from dotenv import load_dotenv
import os

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"
_client = None


def get_client():
    global _client
    if _client is not None:
        return _client

    _api_key = os.getenv("GEMINI_API_KEY")
    if not _api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )

    from google import genai

    _client = genai.Client(api_key=_api_key)
    return _client
