from __future__ import annotations

import math
import queue
import threading
import wave
from typing import Any, Dict, Optional

import numpy as np

_stop_event = threading.Event()
_thread_error: Optional[Exception] = None
_thread_warning: Optional[str] = None
_thread_stats: Dict[str, Any] = {}

_CHUNK = 1024
_SILENCE_RMS_THRESHOLD = 0.001


def _find_loopback_device(p) -> dict:
    import pyaudiowpatch as pyaudio

    if hasattr(p, "get_default_wasapi_loopback"):
        return p.get_default_wasapi_loopback()

    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_output = wasapi_info.get("defaultOutputDevice", -1)
    if default_output == -1:
        raise RuntimeError("No default WASAPI output device found.")

    if hasattr(p, "get_wasapi_loopback_analogue_by_index"):
        return p.get_wasapi_loopback_analogue_by_index(default_output)

    default_device = p.get_device_info_by_index(default_output)
    for index in range(p.get_device_count()):
        device = p.get_device_info_by_index(index)
        if not device.get("isLoopbackDevice", False):
            continue
        if device.get("hostApi") != wasapi_info["index"]:
            continue
        if default_device.get("name", "") in device.get("name", ""):
            return device

    for index in range(p.get_device_count()):
        device = p.get_device_info_by_index(index)
        if device.get("isLoopbackDevice", False):
            return device

    raise RuntimeError(
        "No WASAPI loopback device found. System audio capture is only "
        "available on supported Windows output devices."
    )


def _device_channels(device: dict) -> int:
    channels = int(
        device.get("maxInputChannels")
        or device.get("maxOutputChannels")
        or 2
    )
    return max(1, min(channels, 2))


def record_system_audio(
    filename: str = "speaker.wav",
    stop_event: Optional[threading.Event] = None,
) -> None:

    global _thread_error, _thread_warning, _thread_stats

    event = stop_event or _stop_event
    _thread_error = None
    _thread_warning = None
    _thread_stats = {}
    if stop_event is None:
        event.clear()

    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        _thread_error = ImportError(
            "pyaudiowpatch is not installed. System audio capture is unavailable."
        )
        return

    p = None
    stream = None
    frames_written = 0
    sample_count = 0
    sum_squares = 0.0
    peak = 0.0
    rate = 48000
    channels = 2

    audio_queue: queue.Queue[Optional[bytes]] = queue.Queue(maxsize=256)

    def _callback(in_data, frame_count, time_info, status):
        import pyaudiowpatch as pa
        try:
            audio_queue.put_nowait(in_data)
        except queue.Full:
            pass  # drop the chunk rather than block the C callback
        return (None, pa.paContinue)

    try:
        p = pyaudio.PyAudio()
        device = _find_loopback_device(p)
        channels = _device_channels(device)
        rate = int(device.get("defaultSampleRate") or 48000)

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=int(device["index"]),
            frames_per_buffer=_CHUNK,
            stream_callback=_callback,
        )
        stream.start_stream()

        sample_width = p.get_sample_size(pyaudio.paInt16)
        with wave.open(filename, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(sample_width)
            wav.setframerate(rate)

            while not event.is_set() or not audio_queue.empty():
                try:
                    data = audio_queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                if data is None:
                    break

                wav.writeframes(data)
                samples = np.frombuffer(data, dtype=np.int16)
                if samples.size:
                    normalised = samples.astype(np.float32) / 32768.0
                    frames_written += int(samples.size / channels)
                    sample_count += int(samples.size)
                    sum_squares += float(np.sum(np.square(normalised, dtype=np.float64)))
                    peak = max(peak, float(np.max(np.abs(normalised))))

    except Exception as exc:
        _thread_error = exc
        return
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if p is not None:
            p.terminate()

    duration = frames_written / rate if rate else 0.0
    rms = math.sqrt(sum_squares / sample_count) if sample_count else 0.0
    _thread_stats = {
        "path": filename,
        "samplerate": rate,
        "channels": channels,
        "duration": duration,
        "frames": frames_written,
        "rms": rms,
        "peak": peak,
        "silent": rms < _SILENCE_RMS_THRESHOLD,
    }

    if duration < 0.25:
        _thread_error = RuntimeError("System audio recording was too short to transcribe.")
        return
    if rms < _SILENCE_RMS_THRESHOLD:
        _thread_warning = "System audio captured near-silence."


def stop_system_audio() -> None:
    _stop_event.set()


def get_error() -> Optional[Exception]:
    return _thread_error


def get_warning() -> Optional[str]:
    return _thread_warning


def get_stats() -> Dict[str, Any]:
    return dict(_thread_stats)
