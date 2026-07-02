"""
Audio transcription via OpenAI Whisper + optional speaker diarization
and per-segment sentiment analysis.

Fixes:
- Removed emoji comments (🔥 NEW etc.)
- find_speaker() now returns the speaker with MAXIMUM overlap over the
  Whisper segment rather than the first speaker with any overlap.
  The old logic incorrectly assigned the speaker who started first
  rather than the one who spoke most during the segment.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections import defaultdict
from typing import Any, Dict, List

import torch
import whisper

from core.diarizer import diarize
from core.sentiment import get_sentiment, get_dominant_sentiment

device = "cuda" if torch.cuda.is_available() else "cpu"
_model = None


def _get_model():
    global _model
    if _model is None:
        # "tiny" uses ~150 MB RAM vs "small" at ~460 MB.
        # On CPU-only machines running pyannote simultaneously,
        # "small" causes Windows to kill the process due to memory pressure.
        # "tiny" is fast enough for meeting transcription at acceptable accuracy.
        _model = whisper.load_model("tiny").to(device)
    return _model


def convert_video_to_audio(video_path: str) -> str:
    """
    Extract audio from any media file and return a path to a 16 kHz mono WAV.

    WAV (not MP3) is used because:
    1. soundfile.read() in diarizer.py requires a format it can decode natively.
       libsndfile (which soundfile wraps) does NOT support MP3 on most systems,
       so diarize() was silently catching the error and returning [] — causing
       every transcript segment to be labelled "Unknown".
    2. WAV is lossless. Converting to MP3 first introduced compression artifacts
       that degraded Whisper transcription quality, especially for recordings
       captured at 16 kHz from merge.py (double re-encoding).
    3. Whisper accepts WAV natively and handles its own resampling internally.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio_path = temp_file.name
    temp_file.close()
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-ar", "16000",   # resample to Whisper's native rate
            "-ac", "1",        # mono
            "-c:a", "pcm_s16le",
            audio_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return audio_path


def find_speaker(
    segment: Dict,
    diarization: List[Dict],
    tolerance: float = 0.75,
) -> str:
    """
    Return the speaker label with the greatest time overlap with `segment`.

    Previously returned the FIRST speaker with any overlap, which gave
    wrong results when a Whisper segment spanned a speaker boundary
    (the speaker who started first "won" regardless of how little they spoke).
    Now picks the speaker who occupied the most time in the segment.
    """
    seg_start = segment["start"]
    seg_end = segment["end"]

    if not diarization:
        return "Unknown"

    best_speaker = "Unknown"
    best_overlap = 0.0
    segment_midpoint = (seg_start + seg_end) / 2

    for spk in diarization:
        overlap = max(
            0.0,
            min(seg_end, spk["end"]) - max(seg_start, spk["start"])
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = spk["speaker"]

    if best_overlap > 0:
        return best_speaker

    nearest_speaker = "Unknown"
    nearest_gap = None
    for spk in diarization:
        if segment_midpoint < spk["start"]:
            gap = spk["start"] - segment_midpoint
        elif segment_midpoint > spk["end"]:
            gap = segment_midpoint - spk["end"]
        else:
            gap = 0.0

        if nearest_gap is None or gap < nearest_gap:
            nearest_gap = gap
            nearest_speaker = spk["speaker"]

    if nearest_gap is not None and nearest_gap <= tolerance:
        return nearest_speaker

    return best_speaker


def transcribe_video(video_path: str) -> Dict[str, Any]:
    audio_path = None
    try:
        audio_path = convert_video_to_audio(video_path)

        result = _get_model().transcribe(audio_path, fp16=torch.cuda.is_available())
        diarization = diarize(audio_path)  # returns [] if unavailable

        segments: List[Dict] = []
        for seg in result.get("segments", []):
            text = seg["text"]
            sentiment = get_sentiment(text)
            segments.append({
                "speaker": find_speaker(seg, diarization),
                "start": seg["start"],
                "end": seg["end"],
                "text": text,
                "sentiment": sentiment["label"],
                "sentiment_score": sentiment["score"],
            })

        # Speaker-level dominant sentiment (computed once here, not duplicated in app.py)

        speaker_sentiment_map: Dict[str, List[str]] = defaultdict(list)
        for seg in segments:
            speaker_sentiment_map[seg["speaker"]].append(seg["sentiment"])

        speaker_sentiment = {
            spk: get_dominant_sentiment(sents)
            for spk, sents in speaker_sentiment_map.items()
        }

        all_sentiments = [seg["sentiment"] for seg in segments]
        overall_sentiment = (
            get_dominant_sentiment(all_sentiments) if all_sentiments else "NEUTRAL"
        )

        return {
            "text": result.get("text", ""),
            "language": result.get("language", "unknown"),
            "segments": segments,
            "speaker_turns": diarization,
            "duration": segments[-1]["end"] if segments else 0,
            "speaker_sentiment": speaker_sentiment,
            "overall_sentiment": overall_sentiment,
        }

    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
