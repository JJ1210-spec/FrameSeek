"""
API schemas (request / response bodies).
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

JobStatus = Literal["queued", "running", "completed", "failed"]

WHISPER_MODELS = (
    "tiny.en", "tiny", "base.en", "base", "small.en", "small",
    "medium.en", "medium", "large-v3",
)


class JobOptions(BaseModel):
    """Tuning knobs — mirror the CLI flags of the core package."""

    model: Optional[str] = Field(None, description="Model for short/medium tier (default: tiny.en on CPU)")
    coarse_model: str = "tiny.en"
    fine_model: str = "tiny.en"
    verify_model: str = Field("base.en", description="Confirms near-miss matches on a ±45 s window")
    language: Optional[str] = Field(
        None, pattern=r"^[a-z]{2,3}$", description="Spoken language code; empty = auto-detect"
    )
    match_threshold: float = Field(80.0, ge=0, le=100)
    coarse_threshold: float = Field(50.0, ge=0, le=100)
    window_buffer: float = Field(45.0, gt=0, le=600)
    cpu_threads: Optional[int] = Field(None, ge=1, le=64)
    cookies_from_browser: Optional[Literal["chrome", "firefox", "edge", "brave", "opera", "safari"]] = None

    @field_validator("model", "coarse_model", "fine_model", "verify_model")
    @classmethod
    def _known_model(cls, value):
        if value is not None and value not in WHISPER_MODELS:
            raise ValueError(f"Unknown model '{value}'. Choose one of: {', '.join(WHISPER_MODELS)}")
        return value


class UrlJobCreate(BaseModel):
    source_url: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=1000)
    options: JobOptions = Field(default_factory=JobOptions)

    @field_validator("source_url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith(("http://", "https://")):
            raise ValueError("source_url must start with http:// or https://")
        return value

    @field_validator("query")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class Job(BaseModel):
    id: str
    status: JobStatus
    source_url: str
    query: str
    options: JobOptions
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    current_stage: Optional[str] = None
    stage_history: list[str] = Field(default_factory=list)
    queue_position: Optional[int] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    has_frame: bool = False


class JobSummary(BaseModel):
    id: str
    status: JobStatus
    source_url: str
    query: str
    created_at: datetime
    finished_at: Optional[datetime] = None
    result_status: Optional[str] = None
    has_frame: bool = False


class JobLogs(BaseModel):
    id: str
    lines: list[str]
    total: int


class DependencyCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class HealthReport(BaseModel):
    status: Literal["ok"] = "ok"
    ready: bool = Field(..., description="True when every pipeline dependency is available")
    version: str
    checks: list[DependencyCheck]
