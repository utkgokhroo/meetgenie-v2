import whisper
import torch
import os
import subprocess
from diarizer import diarize

# 🔥 NEW
from sentiment import get_sentiment
from collections import defaultdict

device = "cuda" if torch.cuda.is_available() else "cpu"

model = whisper.load_model("small").to(device)


def convert_video_to_audio(video_path):
    audio_path = "temp_audio.mp3"

    subprocess.run(
        [
            "ffmpeg",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "mp3",
            audio_path
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return audio_path


def transcribe_video(video_path):
    audio_path = None

    try:
        audio_path = convert_video_to_audio(video_path)

        result = model.transcribe(
            audio_path,
            fp16=torch.cuda.is_available()
        )

        diarization = diarize(audio_path)

        segments = []

        for seg in result.get("segments", []):

            text = seg["text"]

            # 🔥 NEW: sentiment per segment
            sentiment = get_sentiment(text)

            segments.append({
                "speaker": find_speaker(seg, diarization),
                "start": seg["start"],
                "end": seg["end"],
                "text": text,
                "sentiment": sentiment["label"],          # 🔥 NEW
                "sentiment_score": sentiment["score"]     # 🔥 NEW
            })

        # 🔥 NEW: speaker-wise sentiment
        speaker_sentiment_map = defaultdict(list)

        for seg in segments:
            speaker_sentiment_map[seg["speaker"]].append(seg["sentiment"])

        def majority_sentiment(sentiments):
            return max(set(sentiments), key=sentiments.count)

        speaker_sentiment = {
            spk: majority_sentiment(sents)
            for spk, sents in speaker_sentiment_map.items()
        }

        # 🔥 NEW: overall sentiment
        all_sentiments = [seg["sentiment"] for seg in segments]
        overall = majority_sentiment(all_sentiments) if all_sentiments else "NEUTRAL"

        return {
            "text": result.get("text", ""),
            "language": result.get("language", "unknown"),
            "segments": segments,
            "duration": (
                segments[-1]["end"]
                if segments
                else 0
            ),
            "speaker_sentiment": speaker_sentiment,   # 🔥 NEW
            "overall_sentiment": overall              # 🔥 NEW
        }

    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


def find_speaker(segment, diarization):

    start = segment["start"]
    end = segment["end"]

    # 🔥 IMPROVED LOGIC (better than midpoint)
    for speaker_seg in diarization:

        overlap = min(end, speaker_seg["end"]) - max(start, speaker_seg["start"])

        if overlap > 0:
            return speaker_seg["speaker"]

    return "Unknown"