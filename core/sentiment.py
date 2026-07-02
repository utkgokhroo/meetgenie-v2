from __future__ import annotations

from collections import Counter
from typing import Dict, List

# Lazy singleton
_pipeline = None

_LABEL_MAP = {
    "LABEL_0": "NEGATIVE",
    "LABEL_1": "NEUTRAL",
    "LABEL_2": "POSITIVE",
}


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    from transformers import pipeline as hf_pipeline

    _pipeline = hf_pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-roberta-base-sentiment",
    )
    return _pipeline


def get_sentiment(text: str) -> Dict[str, object]:

    if not text or not text.strip():
        return {"label": "NEUTRAL", "score": 0.0}

    try:
        result = _get_pipeline()(text[:512])[0]
        return {
            "label": _LABEL_MAP.get(result["label"], "NEUTRAL"),
            "score": float(result["score"]),
        }
    except Exception as exc:
        print(f"[sentiment] get_sentiment failed: {exc}")
        return {"label": "NEUTRAL", "score": 0.0}


def get_dominant_sentiment(sentiments: List[str]) -> str:
    """
    Return the most common sentiment label from a list.
    Returns "NEUTRAL" for an empty list.
    """
    if not sentiments:
        return "NEUTRAL"
    return Counter(sentiments).most_common(1)[0][0]
