from transcriber import transcribe_video
from summarizer import generate_summary


def process_video(video_path):

    if video_path.lower().endswith(".txt"):

        with open(video_path, "r", encoding="utf-8") as f:
            transcript_text = f.read()

        transcription = {
            "text": transcript_text,
            "language": "text",
            "segments": [],
            "duration": 0
        }

    else:
        transcription = transcribe_video(video_path)

    summary = generate_summary(
        transcription["text"]
    )

    summary["transcript"] = transcription["text"]
    summary["language"] = transcription["language"]
    summary["duration"] = transcription["duration"]
    summary["segments"] = transcription["segments"]

    return summary