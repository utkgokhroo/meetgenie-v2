from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
import warnings
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RecordingSession:
    temp_dir: str
    mic_path: str
    system_path: str
    output_path: str
    stop_event: threading.Event
    mic_thread: threading.Thread
    system_thread: threading.Thread
    started_at: float
    warnings: list[str] = field(default_factory=list)


_session: Optional[RecordingSession] = None


def _new_output_path() -> str:
    fd, path = tempfile.mkstemp(prefix="meetgenie_meeting_", suffix=".wav")
    os.close(fd)
    return path


def _thread_errors() -> list[str]:
    import recording.audio_recorder as audio_recorder
    import recording.system_audio_recorder as system_audio_recorder

    errors = []
    mic_error = audio_recorder.get_error()
    sys_error = system_audio_recorder.get_error()
    if mic_error:
        errors.append(f"Microphone: {mic_error}")
    if sys_error:
        errors.append(f"System audio: {sys_error}")
    return errors


def _thread_warnings() -> list[str]:
    import recording.audio_recorder as audio_recorder
    import recording.system_audio_recorder as system_audio_recorder

    values = []
    for label, warning in (
        ("Microphone", audio_recorder.get_warning()),
        ("System audio", system_audio_recorder.get_warning()),
    ):
        if warning:
            values.append(f"{label}: {warning}")
    return values


def _cleanup_session_files(session: RecordingSession, keep_output: bool) -> None:
    try:
        if not keep_output and os.path.exists(session.output_path):
            os.remove(session.output_path)
    except OSError:
        pass

    try:
        if os.path.isdir(session.temp_dir):
            shutil.rmtree(session.temp_dir)
    except OSError:
        pass


def start_recording() -> None:

    global _session

    if _session is not None and is_recording():
        raise RuntimeError("Recording is already in progress.")

    from recording.audio_recorder import record_microphone
    from recording.system_audio_recorder import record_system_audio

    temp_dir = tempfile.mkdtemp(prefix="meetgenie_recording_")
    mic_path = os.path.join(temp_dir, "microphone.wav")
    system_path = os.path.join(temp_dir, "system.wav")
    output_path = _new_output_path()
    stop_event = threading.Event()

    mic_thread = threading.Thread(
        target=record_microphone,
        kwargs={"filename": mic_path, "stop_event": stop_event},
        daemon=True,
        name="MeetGenieMicRecorder",
    )
    system_thread = threading.Thread(
        target=record_system_audio,
        kwargs={"filename": system_path, "stop_event": stop_event},
        daemon=True,
        name="MeetGenieSystemRecorder",
    )

    _session = RecordingSession(
        temp_dir=temp_dir,
        mic_path=mic_path,
        system_path=system_path,
        output_path=output_path,
        stop_event=stop_event,
        mic_thread=mic_thread,
        system_thread=system_thread,
        started_at=time.time(),
    )

    mic_thread.start()
    system_thread.start()

    time.sleep(0.2)
    if not mic_thread.is_alive() and not system_thread.is_alive():
        errors = _thread_errors()
        _cleanup_session_files(_session, keep_output=False)
        _session = None
        raise RuntimeError("; ".join(errors) if errors else "Recording could not start.")


def stop_recording() -> str:

    global _session

    if _session is None:
        raise RuntimeError("No recording is in progress.")

    session = _session
    session.stop_event.set()

    session.mic_thread.join(timeout=30)
    session.system_thread.join(timeout=30)

    alive = [
        thread.name
        for thread in (session.mic_thread, session.system_thread)
        if thread.is_alive()
    ]
    if alive:
        errors = _thread_errors()
        detail = "; ".join(errors) if errors else "thread did not exit after 30s"
        _cleanup_session_files(session, keep_output=False)
        _session = None
        raise RuntimeError(
            f"Recording did not stop cleanly ({', '.join(alive)}): {detail}"
        )

    from recording.merge import merge_recordings

    errors = _thread_errors()
    session.warnings.extend(_thread_warnings())

    try:
        output_path = merge_recordings(
            mic=session.mic_path,
            speaker=session.system_path,
            output=session.output_path,
        )
    except Exception as merge_err:
        detail = "; ".join(errors) if errors else str(merge_err)
        _cleanup_session_files(session, keep_output=False)
        _session = None
        raise RuntimeError(f"Recording failed: {detail}") from merge_err

    _cleanup_session_files(session, keep_output=True)
    _session = None

    if errors:
        session.warnings.extend(errors)
    if session.warnings:
        warnings.warn(
            "Recording completed with warnings: " + "; ".join(session.warnings),
            stacklevel=2,
        )

    return output_path


def get_recording_duration() -> float:
    if _session is None:
        return 0.0
    return time.time() - _session.started_at


def is_recording() -> bool:
    if _session is None:
        return False
    return _session.mic_thread.is_alive() or _session.system_thread.is_alive()
