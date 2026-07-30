"""
Shared fixtures for the API and service tests (fakes live in ``tests/fakes.py``).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

from .fakes import fake_success_run


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        cors_origins=["http://localhost:5173"],
    )


@pytest.fixture
def make_client(settings):
    """Factory: ``make_client(run_fn)`` → started TestClient (worker running)."""
    clients = []

    def _make(run_fn=fake_success_run):
        app = create_app(settings=settings, run_fn=run_fn)
        client = TestClient(app)
        client.__enter__()  # runs lifespan → starts the worker
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)
