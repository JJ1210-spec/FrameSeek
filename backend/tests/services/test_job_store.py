import json

import pytest

from app.schemas import JobOptions
from app.services import job_store as job_store_module
from app.services.job_store import JobNotFound, JobStore


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "jobs")


def _create(store, query="hello"):
    return store.create(source_url="https://example.com/v", query=query, options=JobOptions())


def test_create_persists_job_json(store, tmp_path):
    job = _create(store)
    data = json.loads((tmp_path / "jobs" / job.id / "job.json").read_text(encoding="utf-8"))
    assert data["id"] == job.id
    assert data["status"] == "queued"
    assert data["source_url"] == "https://example.com/v"


def test_get_returns_a_copy(store):
    job = _create(store)
    copy = store.get(job.id)
    copy.status = "failed"
    assert store.get(job.id).status == "queued"


def test_get_unknown_raises(store):
    with pytest.raises(JobNotFound):
        store.get("nope")
    with pytest.raises(JobNotFound):
        store.update("nope", status="running")
    with pytest.raises(JobNotFound):
        store.logs("nope")
    with pytest.raises(JobNotFound):
        store.delete("nope")


def test_enter_stage_tracks_current_and_history(store):
    job = _create(store)
    store.enter_stage(job.id, "acquire_video")
    store.enter_stage(job.id, "get_video_metadata")
    reloaded = store.get(job.id)
    assert reloaded.current_stage == "get_video_metadata"
    assert reloaded.stage_history == ["acquire_video", "get_video_metadata"]
    store.enter_stage("unknown", "x")  # ignored, no error


def test_jobs_reload_from_disk_and_interrupted_jobs_fail(tmp_path):
    first = JobStore(tmp_path / "jobs")
    done = _create(first, "done")
    first.update(done.id, status="completed", result={"status": "success"})
    running = _create(first, "running")
    first.update(running.id, status="running", current_stage="transcribe")
    queued = _create(first, "queued")
    first.append_log(done.id, "line 1")
    first.append_log(done.id, "line 2")

    second = JobStore(tmp_path / "jobs")  # simulates a server restart
    assert {j.id for j in second.list_jobs()} == {done.id, running.id, queued.id}
    assert second.get(done.id).status == "completed"
    assert second.get(done.id).result == {"status": "success"}
    for job_id in (running.id, queued.id):
        job = second.get(job_id)
        assert job.status == "failed"
        assert "Server stopped" in job.error
        assert job.current_stage is None
        assert job.finished_at is not None
    assert second.logs(done.id) == (["line 1", "line 2"], 2)


def test_corrupt_job_folder_is_ignored(tmp_path):
    bad = tmp_path / "jobs" / "broken"
    bad.mkdir(parents=True)
    (bad / "job.json").write_text("{not json", encoding="utf-8")
    assert JobStore(tmp_path / "jobs").list_jobs() == []


def test_log_memory_cap_keeps_offsets_absolute(store, monkeypatch):
    monkeypatch.setattr(job_store_module, "MAX_LOG_LINES_IN_MEMORY", 5)
    job = _create(store)
    for i in range(12):
        store.append_log(job.id, f"line {i}")

    lines, total = store.logs(job.id)
    assert total == 12
    assert lines == [f"line {i}" for i in range(7, 12)]
    assert store.logs(job.id, offset=10) == (["line 10", "line 11"], 12)
    # All lines still on disk
    log_file = store.job_dir(job.id) / "logs.txt"
    assert len(log_file.read_text(encoding="utf-8").splitlines()) == 12


def test_video_path_ignores_partial_downloads(store):
    job = _create(store)
    job_dir = store.job_dir(job.id)
    assert store.video_path(job.id) is None
    (job_dir / "input_video.mp4.part").write_bytes(b"x")
    assert store.video_path(job.id) is None
    (job_dir / "input_video.mp4").write_bytes(b"x")
    assert store.video_path(job.id) == job_dir / "input_video.mp4"


def test_remove_scratch_files(store):
    job = _create(store)
    job_dir = store.job_dir(job.id)
    for name in ("audio.wav", "audio_candidate_slice.wav", "matched_frame.jpg"):
        (job_dir / name).write_bytes(b"x")
    store.remove_scratch_files(job.id)
    assert not (job_dir / "audio.wav").exists()
    assert not (job_dir / "audio_candidate_slice.wav").exists()
    assert (job_dir / "matched_frame.jpg").exists()
