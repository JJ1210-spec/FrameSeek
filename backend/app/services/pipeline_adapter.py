"""
Bridge between the web API and the ``frame_finder`` pipeline package.

``frame_finder`` is imported lazily (on the first job) so the API starts in
well under a second and ``/api/health`` can report missing dependencies
instead of the server failing to boot.
"""

import json
from pathlib import Path
from typing import Callable

from ..schemas import Job
from .log_capture import capture_thread_output


def run_job(
    job: Job,
    job_dir: Path,
    on_stage: Callable[[str], None],
    log: Callable[[str], None],
) -> dict:
    """Configure the pipeline for *job*, run it, and save ``result.json``.

    Returns the cleaned pipeline result (``None`` values dropped, exactly as the
    CLI writes it).
    """
    with capture_thread_output(log):
        from frame_finder.main import configure
        from frame_finder.pipeline import run_pipeline

        configure(outdir=str(job_dir), **job.options.model_dump())

        print(f"[INFO] Query  : {job.query}")
        print(f"[INFO] Source : {job.source_url}")
        print()

        result = run_pipeline(job.source_url, job.query, on_stage=on_stage)

    clean = {k: v for k, v in result.items() if v is not None}
    (Path(job_dir) / "result.json").write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return clean
