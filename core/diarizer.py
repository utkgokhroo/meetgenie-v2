from __future__ import annotations

from dotenv import load_dotenv
import os
import torch
import soundfile as sf
from typing import List, Dict, Any

load_dotenv()

_pipeline = None


def _get_hf_token() -> str:
    for name in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        token = os.getenv(name)
        if token:
            return token
    raise EnvironmentError(
        "HF_TOKEN is not set. Add your HuggingFace token to .env to enable "
        "speaker diarization. Get one at https://huggingface.co/settings/tokens"
    )


def _get_pipeline():
    """Load the pyannote pipeline once and cache it for the process lifetime."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    from pyannote.audio import Pipeline

    token = _get_hf_token()

    try:
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=token,
        )
    except TypeError:
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=token,
        )

    if torch.cuda.is_available() and hasattr(_pipeline, "to"):
        _pipeline.to(torch.device("cuda"))

    return _pipeline


def _speaker_label(raw_speaker: str, speaker_map: Dict[str, str]) -> str:
    if raw_speaker not in speaker_map:
        speaker_map[raw_speaker] = f"Speaker {len(speaker_map) + 1}"
    return speaker_map[raw_speaker]


def _normalise_turns(diarization) -> List[Dict[str, Any]]:
    raw_turns: List[Dict[str, Any]] = []

    for segment, _, raw_speaker in diarization.itertracks(yield_label=True):
        start = float(segment.start)
        end = float(segment.end)
        if end <= start:
            continue

        raw_turns.append({
            "raw_speaker": str(raw_speaker),
            "start": start,
            "end": end,
        })

    speaker_map: Dict[str, str] = {}
    turns: List[Dict[str, Any]] = []
    for turn in sorted(raw_turns, key=lambda item: (item["start"], item["end"])):
        raw_speaker = turn["raw_speaker"]
        turns.append({
            "speaker": _speaker_label(raw_speaker, speaker_map),
            "raw_speaker": raw_speaker,
            "start": turn["start"],
            "end": turn["end"],
        })

    return turns


def diarize(audio_path: str) -> List[Dict[str, Any]]:
    try:
        pipeline = _get_pipeline()
    except Exception as exc:
        # Diarization is optional — log and degrade gracefully.
        print(f"[diarizer] Skipping diarization: {exc}")
        return []

    try:
        audio, sample_rate = sf.read(audio_path)
        sample_rate = int(sample_rate)  # numpy int64 -> plain int (required by pyannote)

        # Build waveform tensor expected by pyannote
        if audio.ndim == 1:
            waveform = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        else:
            waveform = torch.tensor(audio.T, dtype=torch.float32)

        raw_output = pipeline({"waveform": waveform, "sample_rate": sample_rate})

        if hasattr(raw_output, "speaker_diarization"):
            annotation = raw_output.speaker_diarization
        elif hasattr(raw_output, "diarization"):
            annotation = raw_output.diarization
        else:
            annotation = raw_output

        return _normalise_turns(annotation)

    except Exception as exc:
        print(f"[diarizer] Diarization failed: {exc}")
        return []
