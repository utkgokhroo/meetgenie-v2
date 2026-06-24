from transformers import pipeline

sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment"
)

def get_sentiment(text):
    if not text.strip():
        return {"label": "NEUTRAL", "score": 0.0}

    result = sentiment_pipeline(text[:512])[0]

    label_map = {
        "LABEL_0": "NEGATIVE",
        "LABEL_1": "NEUTRAL",
        "LABEL_2": "POSITIVE"
    }

    return {
        "label": label_map[result["label"]],
        "score": float(result["score"])
    }