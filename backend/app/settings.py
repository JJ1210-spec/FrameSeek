"""
Backend settings — read once from environment variables.

| Variable            | Default                          | Meaning                              |
|---------------------|----------------------------------|--------------------------------------|
| DFF_DATA_DIR        | backend/data                     | Where per-job folders are stored     |
| DFF_CORS_ORIGINS    | http://localhost:5173,...        | Comma-separated allowed origins      |
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _split_csv(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Settings:
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("DFF_DATA_DIR", BACKEND_DIR / "data")).resolve()
    )
    cors_origins: list = field(
        default_factory=lambda: _split_csv(
            os.environ.get(
                "DFF_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            )
        )
    )

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"
