"""
Job worker — runs queued jobs one at a time on a background thread.

The core package keeps its settings in module-level globals (``config.py``),
so two pipelines must never run concurrently in one process.  A single worker
thread with a FIFO queue guarantees that, and keeps loaded Whisper / VAD
models cached between jobs.
"""

import queue
import threading
import traceback
from pathlib import Path
from typing import Callable, Optional

from ..schemas import Job
from .job_store import JobNotFound, JobStore, utcnow

# (job, job_dir, on_stage, log) -> result dict
RunFn = Callable[[Job, Path, Callable[[str], None], Callable[[str], None]], dict]

_STOP = object()


class JobWorker:
    def __init__(self, store: JobStore, run_fn: RunFn):
        self._store = store
        self._run_fn = run_fn
        self._queue: "queue.Queue" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._idle = threading.Event()
        self._idle.set()

    # ---- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="dff-job-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if not self._thread:
            return
        self._queue.put(_STOP)
        self._thread.join(timeout)
        self._thread = None

    def submit(self, job_id: str) -> None:
        self._idle.clear()
        self._queue.put(job_id)

    def wait_until_idle(self, timeout: float = 10.0) -> bool:
        """Block until the queue is drained (used by tests)."""
        return self._idle.wait(timeout)

    # ---- worker loop -------------------------------------------------------

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            try:
                self._process(item)
            finally:
                if self._queue.empty():
                    self._idle.set()

    def _process(self, job_id: str) -> None:
        try:
            job = self._store.get(job_id)
        except JobNotFound:
            return  # deleted while queued
        if job.status != "queued":
            return

        self._store.update(job_id, status="running", started_at=utcnow())
        log = lambda line: self._store.append_log(job_id, line)  # noqa: E731
        on_stage = lambda stage: self._store.enter_stage(job_id, stage)  # noqa: E731
        job_dir = self._store.job_dir(job_id)

        try:
            result = self._run_fn(job, job_dir, on_stage, log)
        except BaseException as exc:  # noqa: BLE001 — the worker must survive anything
            for line in traceback.format_exc().rstrip().splitlines():
                log(line)
            self._finish(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
            return

        self._finish(job_id, status="completed", result=result)

    def _finish(self, job_id: str, **fields) -> None:
        if not self._store.exists(job_id):
            return
        self._store.remove_scratch_files(job_id)
        self._store.update(
            job_id,
            finished_at=utcnow(),
            current_stage=None,
            has_frame=self._store.frame_path(job_id).is_file(),
            **fields,
        )
