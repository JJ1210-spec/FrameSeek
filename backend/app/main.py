"""
FastAPI application factory.

Run locally::

    cd backend
    uvicorn app.main:app --port 8000
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import health, jobs
from .services import pipeline_adapter
from .services.job_store import JobStore
from .services.job_worker import JobWorker, RunFn
from .settings import Settings


def create_app(settings: Optional[Settings] = None, run_fn: Optional[RunFn] = None) -> FastAPI:
    """Build the app.  Tests pass a temp-dir *settings* and a fake *run_fn*."""
    settings = settings or Settings()
    if run_fn is None:
        run_fn = pipeline_adapter.run_job

    store = JobStore(settings.jobs_dir)
    worker = JobWorker(store, run_fn)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(
        title="FrameSeek API",
        version=__version__,
        description="CPU-Optimized Speech-to-Frame Localization Pipeline — "
                    "find the exact video frame where a dialogue line is spoken.",
        license_info={"name": "MIT", "identifier": "MIT"},
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = store
    app.state.worker = worker

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    return app


app = create_app()
