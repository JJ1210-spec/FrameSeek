"""
Job store — thread-safe, in-memory, persisted to one folder per job.

Layout on disk::

    <jobs_dir>/<job_id>/
        job.json            job metadata (rewritten on every state change)
        logs.txt            pipeline console output (append-only)
        input_video.mp4     downloaded video (written by the core package)
        matched_frame.jpg   result frame (written by the core package)
        result.json         pipeline result
"""

import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..schemas import Job, JobOptions

MAX_LOG_LINES_IN_MEMORY = 2000
FRAME_FILENAME = "matched_frame.jpg"
DOWNLOAD_STEM = "input_video"
SCRATCH_FILES = ("audio.wav", "audio_candidate_slice.wav")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobNotFound(KeyError):
    pass


class JobStore:
    def __init__(self, jobs_dir: Path):
        self._jobs_dir = Path(jobs_dir)
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._logs: dict[str, list[str]] = {}
        self._log_totals: dict[str, int] = {}
        self._load_from_disk()

    # ---- persistence -------------------------------------------------------

    def _load_from_disk(self) -> None:
        for job_file in self._jobs_dir.glob("*/job.json"):
            try:
                job = Job.model_validate_json(job_file.read_text(encoding="utf-8"))
            except Exception:
                continue  # corrupt / foreign folder — ignore it
            if job.status in ("queued", "running"):
                # The server stopped before this job finished.
                job.status = "failed"
                job.error = "Server stopped before the job finished. Please resubmit."
                job.finished_at = job.finished_at or utcnow()
                job.current_stage = None
            self._jobs[job.id] = job
            lines = self._read_log_file(job.id)
            self._logs[job.id] = lines[-MAX_LOG_LINES_IN_MEMORY:]
            self._log_totals[job.id] = len(lines)
            self._persist(job)

    def _read_log_file(self, job_id: str) -> list[str]:
        log_file = self.job_dir(job_id) / "logs.txt"
        if not log_file.exists():
            return []
        return log_file.read_text(encoding="utf-8", errors="replace").splitlines()

    def _persist(self, job: Job) -> None:
        job_file = self.job_dir(job.id) / "job.json"
        tmp = job_file.with_suffix(".json.tmp")
        tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(job_file)

    # ---- paths -------------------------------------------------------------

    def job_dir(self, job_id: str) -> Path:
        return self._jobs_dir / job_id

    def frame_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / FRAME_FILENAME

    def video_path(self, job_id: str) -> Optional[Path]:
        """The downloaded video for a job, if it exists."""
        for candidate in sorted(self.job_dir(job_id).glob(f"{DOWNLOAD_STEM}.*")):
            if candidate.is_file() and not candidate.name.endswith((".part", ".ytdl")):
                return candidate
        return None

    def remove_scratch_files(self, job_id: str) -> None:
        for name in SCRATCH_FILES:
            (self.job_dir(job_id) / name).unlink(missing_ok=True)

    # ---- CRUD --------------------------------------------------------------

    def create(self, source_url: str, query: str, options: JobOptions) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:12],
            status="queued",
            source_url=source_url,
            query=query,
            options=options,
            created_at=utcnow(),
        )
        with self._lock:
            self.job_dir(job.id).mkdir(parents=True, exist_ok=False)
            self._jobs[job.id] = job
            self._logs[job.id] = []
            self._log_totals[job.id] = 0
            self._persist(job)
            return job.model_copy(deep=True)

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFound(job_id)
            copy = job.model_copy(deep=True)
            copy.queue_position = self._queue_position(job)
            return copy

    def exists(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._jobs

    def list_jobs(self) -> list[Job]:
        with self._lock:
            jobs = [self.get(job_id) for job_id in self._jobs]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def update(self, job_id: str, **fields) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFound(job_id)
            for key, value in fields.items():
                setattr(job, key, value)
            self._persist(job)
            return job.model_copy(deep=True)

    def enter_stage(self, job_id: str, stage: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.current_stage = stage
            job.stage_history.append(stage)
            self._persist(job)

    def delete(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._jobs:
                raise JobNotFound(job_id)
            del self._jobs[job_id]
            self._logs.pop(job_id, None)
            self._log_totals.pop(job_id, None)
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)

    def _queue_position(self, job: Job) -> Optional[int]:
        """Number of jobs ahead of *job* (running job + older queued jobs)."""
        if job.status != "queued":
            return None
        ahead = [
            other for other in self._jobs.values()
            if other.status == "running"
            or (other.status == "queued" and other.created_at < job.created_at)
        ]
        return len(ahead)

    # ---- logs --------------------------------------------------------------

    def append_log(self, job_id: str, line: str) -> None:
        with self._lock:
            if job_id not in self._jobs:
                return
            buffer = self._logs[job_id]
            buffer.append(line)
            if len(buffer) > MAX_LOG_LINES_IN_MEMORY:
                del buffer[: len(buffer) - MAX_LOG_LINES_IN_MEMORY]
            self._log_totals[job_id] += 1
            with open(self.job_dir(job_id) / "logs.txt", "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def logs(self, job_id: str, offset: int = 0) -> tuple[list[str], int]:
        """Return (lines from absolute index *offset*, total line count)."""
        with self._lock:
            if job_id not in self._jobs:
                raise JobNotFound(job_id)
            buffer = self._logs[job_id]
            total = self._log_totals[job_id]
            first_in_memory = total - len(buffer)
            start = max(offset, first_in_memory) - first_in_memory
            return list(buffer[start:]), total


def load_result_file(job_dir: Path) -> Optional[dict]:
    result_file = job_dir / "result.json"
    if not result_file.exists():
        return None
    return json.loads(result_file.read_text(encoding="utf-8"))
