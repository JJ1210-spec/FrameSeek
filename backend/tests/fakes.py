"""
Fake pipeline ``run_fn`` callables and payload helpers for API tests.

The real pipeline (torch + faster-whisper + ffmpeg + network) is replaced by
these fakes so API tests are fast and deterministic.
"""

import threading
from pathlib import Path

FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"fake-jpeg-bytes" + b"\xff\xd9"
FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64

SHORT_TIER_STAGES = [
    "acquire_video", "get_video_metadata", "extract_audio", "run_vad",
    "transcribe", "match_dialogue", "extract_frame",
]

SUCCESS_RESULT = {
    "status": "success",
    "query": "My mind rebels at stagnation",
    "matched_text": "My mind rebels at stagnation.",
    "similarity_score": 100.0,
    "timestamp_sec": 324.68,
    "frame_number": 7785,
    "video_metadata": {"fps": 23.976, "duration_sec": 3261.74, "is_vfr": False},
    "tier_info": {"tier": "short", "model_size": "tiny.en", "total_speech_sec": 12.3},
    "timings": {"total": 1.23},
}


def fake_success_run(job, job_dir, on_stage, log):
    """Behaves like the real pipeline: stages, console output, files on disk."""
    job_dir = Path(job_dir)
    (job_dir / "input_video.mp4").write_bytes(FAKE_MP4)
    (job_dir / "audio.wav").write_bytes(b"RIFF....WAVE")
    for stage in SHORT_TIER_STAGES:
        on_stage(stage)
        log(f"[INFO] running {stage}")
    (job_dir / "matched_frame.jpg").write_bytes(FAKE_JPEG)
    return {**SUCCESS_RESULT, "query": job.query}


def fake_crash_run(job, job_dir, on_stage, log):
    on_stage("acquire_video")
    log("[INFO] about to explode")
    raise RuntimeError("boom")


def fake_no_match_run(job, job_dir, on_stage, log):
    on_stage("acquire_video")
    return {
        "status": "no_match",
        "query": job.query,
        "closest_text": "something else entirely",
        "similarity_score": 21.5,
        "timings": {"total": 0.5},
    }


class BlockingRun:
    """A run_fn that parks inside the pipeline until ``release()`` is called."""

    def __init__(self):
        self.started = threading.Event()
        self._release = threading.Event()
        self.calls = []

    def __call__(self, job, job_dir, on_stage, log):
        self.calls.append(job)
        on_stage("acquire_video")
        self.started.set()
        self._release.wait(10)
        return {**SUCCESS_RESULT, "query": job.query}

    def release(self):
        self._release.set()


def wait_idle(client, timeout: float = 10.0) -> None:
    assert client.app.state.worker.wait_until_idle(timeout), "worker did not finish in time"


def new_job_payload(**overrides) -> dict:
    payload = {
        "source_url": "https://www.youtube.com/watch?v=abc123",
        "query": "My mind rebels at stagnation",
    }
    payload.update(overrides)
    return payload
