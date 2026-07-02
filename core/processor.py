from core.transcriber import transcribe_video
from core.summarizer import generate_summary
from core.speaker_intelligence import (
    calculate_talk_time,
    calculate_participation,
    get_top_speaker
)


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
    speaker_timeline = transcription.get(
        "speaker_turns"
    ) or transcription["segments"]

    talk_time = calculate_talk_time(
        speaker_timeline
    )

    participation = calculate_participation(
        talk_time
    )

    top_speaker = get_top_speaker(
        talk_time
    )
    summary["talk_time"] = talk_time
    summary["participation"] = participation
    summary["top_speaker"] = top_speaker
    summary["speaker_count"] = len(
        talk_time
    )
    summary["transcript"] = transcription["text"]
    summary["language"] = transcription["language"]
    summary["duration"] = transcription["duration"]
    summary["segments"] = transcription["segments"]
    summary["speaker_turns"] = transcription.get(
        "speaker_turns",
        []
    )
    summary["speaker_sentiment"] = transcription.get(
        "speaker_sentiment",
        {}
    )
    summary["overall_sentiment"] = transcription.get(
        "overall_sentiment",
        "NEUTRAL"
    )

    return summary
