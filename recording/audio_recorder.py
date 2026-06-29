from __future__ import annotations

import math
import queue
import threading
from typing import Any, Dict, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

_stop_event = threading.Event()
_thread_error: Exception | None = None
_thread_warning: str | None = None
_thread_stats: Dict[str, Any] = {}

_SILENCE_RMS_THRESHOLD = 0.001
_QUEUE_MAX_BLOCKS = 256


def _default_input_samplerate() -> int:
    try:
        device = sd.query_devices(kind="input")
        rate = int(device.get("default_samplerate") or 48000)
    except Exception:
        rate = 48000
    return max(rate, 16000)


def record_microphone(
    filename: str = "mic.wav",
    samplerate: Optional[int] = None,
    stop_event: Optional[threading.Event] = None,
) -> None:

    global _thread_error, _thread_warning, _thread_stats

    event = stop_event or _stop_event
    _thread_error = None
    _thread_warning = None
    _thread_stats = {}
    if stop_event is None:
        event.clear()

    rate = int(samplerate or _default_input_samplerate())
    blocks: queue.Queue[np.ndarray] = queue.Queue(maxsize=_QUEUE_MAX_BLOCKS)
    status_messages: list[str] = []
    dropped_blocks = 0

    def _callback(indata: np.ndarray, frames: int, time, status) -> None:
        nonlocal dropped_blocks
        if status:
            status_messages.append(str(status))
        try:
            blocks.put_nowait(indata.copy())
        except queue.Full:
            dropped_blocks += 1

    frames_written = 0
    sample_count = 0
    sum_squares = 0.0
    peak = 0.0

    try:
        with sf.SoundFile(
            filename,
            mode="w",
            samplerate=rate,
            channels=1,
            subtype="PCM_16",
        ) as wav:
            with sd.InputStream(
                samplerate=rate,
                channels=1,
                dtype="float32",
                blocksize=0,
                callback=_callback,
            ):
                while not event.is_set() or not blocks.empty():
                    try:
                        chunk = blocks.get(timeout=0.1)
                    except queue.Empty:
                        if event.is_set():
                            break
                        continue

                    if chunk.ndim > 1 and chunk.shape[1] > 1:
                        chunk = np.mean(chunk, axis=1, keepdims=True)

                    chunk = np.clip(chunk, -1.0, 1.0).astype("float32")
                    wav.write(chunk)

                    frames_written += int(chunk.shape[0])
                    sample_count += int(chunk.size)
                    sum_squares += float(np.sum(np.square(chunk, dtype=np.float64)))
                    peak = max(peak, float(np.max(np.abs(chunk))) if chunk.size else 0.0)

    except Exception as exc:
        _thread_error = exc
        return

    duration = frames_written / rate if rate else 0.0
    rms = math.sqrt(sum_squares / sample_count) if sample_count else 0.0
    _thread_stats = {
        "path": filename,
        "samplerate": rate,
        "channels": 1,
        "duration": duration,
        "frames": frames_written,
        "rms": rms,
        "peak": peak,
        "silent": rms < _SILENCE_RMS_THRESHOLD,
        "dropped_blocks": dropped_blocks,
    }

    warnings = []
    if status_messages:
        warnings.append(status_messages[-1])
    if dropped_blocks:
        warnings.append(f"Dropped {dropped_blocks} microphone audio block(s).")
    if duration < 0.25:
        _thread_error = RuntimeError("Microphone recording was too short to transcribe.")
        return
    if rms < _SILENCE_RMS_THRESHOLD:
        warnings.append("Microphone captured near-silence.")

    _thread_warning = " ".join(warnings) if warnings else None


def stop_microphone() -> None:
    _stop_event.set()


def get_error() -> Exception | None:
    return _thread_error


def get_warning() -> str | None:
    return _thread_warning


def get_stats() -> Dict[str, Any]:
    return dict(_thread_stats)
