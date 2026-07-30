"""
The adapter imports the real core package (torch / faster-whisper must be
installed) but the heavy ``run_pipeline`` and ``configure`` calls are faked.
"""

import json
from datetime import datetime, timezone

import pytest

from app.schemas import Job, JobOptions
from app.services import pipeline_adapter

pytest.importorskip("torch")
pytest.importorskip("faster_whisper")


@pytest.fixture
def core():
    import frame_finder.main as core_main
    import frame_finder.pipeline as core_pipeline

    return core_main, core_pipeline


def _job(**options):
    return Job(
        id="abc123def456",
        status="running",
        source_url="https://example.com/video",
        query="Elementary, my dear Watson",
        options=JobOptions(**options),
        created_at=datetime.now(timezone.utc),
    )


def test_run_job_configures_runs_and_writes_result(core, tmp_path, monkeypatch):
    core_main, core_pipeline = core
    configure_calls = []
    stages = []
    lines = []

    def fake_configure(**kwargs):
        configure_calls.append(kwargs)
        print("[INFO] Using device: cpu (threads: 8)")

    def fake_run_pipeline(source, query, on_stage=None):
        assert (source, query) == ("https://example.com/video", "Elementary, my dear Watson")
        on_stage("acquire_video")
        print("[INFO] Downloading video ...")
        on_stage("extract_frame")
        return {"status": "success", "similarity_score": 100.0, "note": None, "frame_number": 42}

    monkeypatch.setattr(core_main, "configure", fake_configure)
    monkeypatch.setattr(core_pipeline, "run_pipeline", fake_run_pipeline)

    result = pipeline_adapter.run_job(
        _job(match_threshold=75, fine_model="small.en"),
        tmp_path, stages.append, lines.append,
    )

    assert result == {"status": "success", "similarity_score": 100.0, "frame_number": 42}
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == result
    assert stages == ["acquire_video", "extract_frame"]
    assert "[INFO] Using device: cpu (threads: 8)" in lines
    assert "[INFO] Downloading video ..." in lines
    assert "[INFO] Query  : Elementary, my dear Watson" in lines

    assert len(configure_calls) == 1
    call = configure_calls[0]
    assert call["outdir"] == str(tmp_path)
    assert call["match_threshold"] == 75
    assert call["fine_model"] == "small.en"
    assert call["coarse_model"] == "tiny.en"


def test_real_configure_populates_core_config(core, tmp_path):
    core_main, _ = core
    from frame_finder import config

    core_main.configure(outdir=str(tmp_path / "out"), device="cpu", cpu_threads=3, match_threshold=66)

    assert config.DEVICE == "cpu"
    assert config.CPU_THREADS == 3
    assert config.MATCH_THRESHOLD == 66
    assert config.TIER_MODEL_MAP == {"short": "tiny.en", "medium": "tiny.en", "long": "tiny.en"}
    assert config.VIDEO_PATH == str(tmp_path / "out" / "input_video.mp4")
    assert config.FRAME_OUT_PATH == str(tmp_path / "out" / "matched_frame.jpg")
    assert (tmp_path / "out").is_dir()
