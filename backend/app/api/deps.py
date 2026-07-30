"""
FastAPI dependencies — pull shared services off ``app.state``.
"""

from fastapi import Request

from ..services.job_store import JobStore
from ..services.job_worker import JobWorker
from ..settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_store(request: Request) -> JobStore:
    return request.app.state.store


def get_worker(request: Request) -> JobWorker:
    return request.app.state.worker
