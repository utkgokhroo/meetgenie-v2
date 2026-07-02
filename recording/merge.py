from __future__ import annotations

import os
import subprocess
import wave
from typing import Dict


def _wav_stats(path: str) -> Dict[str, float]:
    if not os.path.isfile(path):
        return {"ok": False, "duration": 0.0, "frames": 0}
    try:
        with wave.open(path, "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            duration = frames / rate if rate else 0.0
            return {
                "ok": frames > 0 and duration >= 0.25,
                "duration": duration,
                "frames": frames,
                "samplerate": rate,
                "channels": wav.getnchannels(),
            }
    except wave.Error:
        return {"ok": False, "duration": 0.0, "frames": 0}


def _run_ffmpeg(command: list[str]) -> None:
    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def merge_recordings(
    mic: str = "mic.wav",
    speaker: str = "speaker.wav",
    output: str = "meeting.wav",
) -> str:
    mic_ok = bool(_wav_stats(mic)["ok"])
    spk_ok = bool(_wav_stats(speaker)["ok"])

    if not mic_ok and not spk_ok:
        raise FileNotFoundError(
            "No usable audio was captured. Both microphone and system tracks "
            "are missing, empty, or too short."
        )

    if mic_ok and spk_ok:
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", mic,
            "-i", speaker,
            "-filter_complex",
            (
                "[0:a]aresample=16000,"
                "aformat=sample_fmts=fltp:channel_layouts=mono[a0];"
                "[1:a]aresample=16000,"
                "aformat=sample_fmts=fltp:channel_layouts=mono[a1];"
                "[a0][a1]amix=inputs=2:duration=longest:normalize=1[aout]"
            ),
            "-map", "[aout]",
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            output,
        ]
    else:
        source = mic if mic_ok else speaker
        command = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", source,
            "-vn",
            "-map", "0:a:0",
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            output,
        ]

    try:
        _run_ffmpeg(command)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise RuntimeError(f"ffmpeg failed to prepare recording audio: {detail}") from exc

    output_stats = _wav_stats(output)
    if not output_stats["ok"]:
        raise RuntimeError("Merged recording is empty or too short for transcription.")

    return output
