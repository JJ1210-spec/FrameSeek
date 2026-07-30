import pytest

from ..fakes import (
    FAKE_JPEG,
    FAKE_MP4,
    SHORT_TIER_STAGES,
    BlockingRun,
    fake_crash_run,
    fake_no_match_run,
    new_job_payload,
    wait_idle,
)


# ---- creation + validation ---------------------------------------------------


def test_create_job_returns_201_and_queued_job(make_client):
    blocker = BlockingRun()
    client = make_client(blocker)

    res = client.post("/api/jobs", json=new_job_payload())

    assert res.status_code == 201
    job = res.json()
    assert len(job["id"]) == 12
    assert job["status"] in ("queued", "running")
    assert job["source_url"] == "https://www.youtube.com/watch?v=abc123"
    assert job["query"] == "My mind rebels at stagnation"
    assert job["options"]["match_threshold"] == 80.0
    assert job["options"]["coarse_model"] == "tiny.en"
    blocker.release()
    wait_idle(client)


def test_create_job_trims_url_and_query(make_client):
    client = make_client()
    res = client.post(
        "/api/jobs",
        json=new_job_payload(source_url="  https://ok.ru/video/1  ", query="  hello there  "),
    )
    assert res.status_code == 201
    assert res.json()["source_url"] == "https://ok.ru/video/1"
    assert res.json()["query"] == "hello there"
    wait_idle(client)


@pytest.mark.parametrize(
    "payload",
    [
        new_job_payload(source_url="ftp://example.com/video.mp4"),
        new_job_payload(source_url="C:/videos/local.mp4"),
        new_job_payload(source_url=""),
        new_job_payload(query=""),
        new_job_payload(query="     "),
        new_job_payload(query="x" * 1001),
        new_job_payload(options={"match_threshold": 101}),
        new_job_payload(options={"coarse_threshold": -1}),
        new_job_payload(options={"window_buffer": 0}),
        new_job_payload(options={"model": "gpt-4"}),
        new_job_payload(options={"cpu_threads": 0}),
        new_job_payload(options={"cookies_from_browser": "netscape"}),
        new_job_payload(options={"verify_model": "huge"}),
        new_job_payload(options={"language": "Tamil"}),
        new_job_payload(options={"language": "t"}),
        {"query": "missing url"},
        {"source_url": "https://youtu.be/x"},
    ],
)
def test_create_job_rejects_invalid_input(make_client, payload):
    client = make_client()
    res = client.post("/api/jobs", json=payload)
    assert res.status_code == 422
    assert client.get("/api/jobs").json() == []


def test_custom_options_reach_the_pipeline(make_client):
    blocker = BlockingRun()
    client = make_client(blocker)
    options = {
        "model": "base.en",
        "coarse_model": "tiny.en",
        "fine_model": "small.en",
        "match_threshold": 70,
        "coarse_threshold": 40,
        "window_buffer": 30,
        "cpu_threads": 4,
        "cookies_from_browser": "firefox",
        "verify_model": "small.en",
        "language": "ta",
    }
    client.post("/api/jobs", json=new_job_payload(options=options))
    assert blocker.started.wait(5)
    blocker.release()
    wait_idle(client)

    received = blocker.calls[0].options.model_dump()
    assert received == {**options, "match_threshold": 70.0, "coarse_threshold": 40.0, "window_buffer": 30.0}


# ---- lifecycle ---------------------------------------------------------------


def test_successful_job_lifecycle(make_client):
    client = make_client()
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["error"] is None
    assert job["current_stage"] is None
    assert job["stage_history"] == SHORT_TIER_STAGES
    assert job["has_frame"] is True
    assert job["started_at"] is not None
    assert job["finished_at"] is not None
    assert job["result"]["status"] == "success"
    assert job["result"]["frame_number"] == 7785
    assert job["result"]["timestamp_sec"] == 324.68


def test_scratch_audio_files_are_removed_after_job(make_client, settings):
    client = make_client()
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    job_dir = settings.jobs_dir / job_id
    assert not (job_dir / "audio.wav").exists()
    assert (job_dir / "input_video.mp4").exists()
    assert (job_dir / "matched_frame.jpg").exists()
    assert (job_dir / "job.json").exists()


def test_crashing_pipeline_marks_job_failed_and_logs_traceback(make_client):
    client = make_client(fake_crash_run)
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert job["error"] == "RuntimeError: boom"
    assert job["result"] is None
    assert job["has_frame"] is False

    lines = client.get(f"/api/jobs/{job_id}/logs").json()["lines"]
    assert "[INFO] about to explode" in lines
    assert any("Traceback" in line for line in lines)
    assert lines[-1] == "RuntimeError: boom"


def test_worker_survives_a_crash_and_runs_the_next_job(make_client):
    calls = []

    def flaky(job, job_dir, on_stage, log):
        calls.append(job.query)
        if job.query == "first":
            raise ValueError("bad first job")
        return {"status": "success", "query": job.query}

    client = make_client(flaky)
    first = client.post("/api/jobs", json=new_job_payload(query="first")).json()["id"]
    second = client.post("/api/jobs", json=new_job_payload(query="second")).json()["id"]
    wait_idle(client)

    assert calls == ["first", "second"]
    assert client.get(f"/api/jobs/{first}").json()["status"] == "failed"
    assert client.get(f"/api/jobs/{second}").json()["status"] == "completed"


def test_no_match_result_is_a_completed_job_without_frame(make_client):
    client = make_client(fake_no_match_run)
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["result"]["status"] == "no_match"
    assert job["result"]["closest_text"] == "something else entirely"
    assert job["has_frame"] is False
    assert client.get(f"/api/jobs/{job_id}/frame").status_code == 404


def test_jobs_run_one_at_a_time_in_fifo_order(make_client):
    blocker = BlockingRun()
    client = make_client(blocker)

    first = client.post("/api/jobs", json=new_job_payload(query="one")).json()["id"]
    assert blocker.started.wait(5)
    second = client.post("/api/jobs", json=new_job_payload(query="two")).json()["id"]
    third = client.post("/api/jobs", json=new_job_payload(query="three")).json()["id"]

    running = client.get(f"/api/jobs/{first}").json()
    assert running["status"] == "running"
    assert running["current_stage"] == "acquire_video"
    assert running["queue_position"] is None

    assert client.get(f"/api/jobs/{second}").json()["status"] == "queued"
    assert client.get(f"/api/jobs/{second}").json()["queue_position"] == 1
    assert client.get(f"/api/jobs/{third}").json()["queue_position"] == 2

    blocker.release()
    wait_idle(client)
    assert [job.query for job in blocker.calls] == ["one", "two", "three"]


# ---- reads -------------------------------------------------------------------


def test_list_jobs_newest_first_with_result_status(make_client):
    client = make_client()
    a = client.post("/api/jobs", json=new_job_payload(query="alpha")).json()["id"]
    wait_idle(client)
    b = client.post("/api/jobs", json=new_job_payload(query="beta")).json()["id"]
    wait_idle(client)

    jobs = client.get("/api/jobs").json()
    assert [j["id"] for j in jobs] == [b, a]
    assert jobs[0]["query"] == "beta"
    assert jobs[0]["result_status"] == "success"
    assert jobs[0]["has_frame"] is True
    assert set(jobs[0]) == {
        "id", "status", "source_url", "query", "created_at",
        "finished_at", "result_status", "has_frame",
    }


def test_logs_support_offset(make_client):
    client = make_client()
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    full = client.get(f"/api/jobs/{job_id}/logs").json()
    assert full["total"] == len(SHORT_TIER_STAGES)
    assert full["lines"][0] == "[INFO] running acquire_video"

    tail = client.get(f"/api/jobs/{job_id}/logs", params={"offset": 5}).json()
    assert tail["lines"] == full["lines"][5:]
    assert tail["total"] == full["total"]

    past_end = client.get(f"/api/jobs/{job_id}/logs", params={"offset": 999}).json()
    assert past_end["lines"] == []

    assert client.get(f"/api/jobs/{job_id}/logs", params={"offset": -1}).status_code == 422


def test_frame_endpoint_serves_jpeg(make_client):
    client = make_client()
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    res = client.get(f"/api/jobs/{job_id}/frame")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert res.content == FAKE_JPEG


def test_video_endpoint_serves_downloaded_video_with_range_support(make_client):
    client = make_client()
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    res = client.get(f"/api/jobs/{job_id}/video")
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    assert res.content == FAKE_MP4

    partial = client.get(f"/api/jobs/{job_id}/video", headers={"Range": "bytes=0-9"})
    assert partial.status_code == 206
    assert partial.content == FAKE_MP4[:10]


def test_video_not_available_while_running(make_client):
    blocker = BlockingRun()
    client = make_client(blocker)
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    assert blocker.started.wait(5)

    assert client.get(f"/api/jobs/{job_id}/video").status_code == 404
    blocker.release()
    wait_idle(client)


@pytest.mark.parametrize("suffix", ["", "/logs", "/frame", "/video"])
def test_unknown_job_returns_404(make_client, suffix):
    client = make_client()
    res = client.get(f"/api/jobs/doesnotexist{suffix}")
    assert res.status_code == 404
    assert "detail" in res.json()


# ---- delete ------------------------------------------------------------------


def test_delete_finished_job_removes_it_and_its_files(make_client, settings):
    client = make_client()
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    wait_idle(client)

    assert client.delete(f"/api/jobs/{job_id}").status_code == 204
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.get("/api/jobs").json() == []
    assert not (settings.jobs_dir / job_id).exists()
    assert client.delete(f"/api/jobs/{job_id}").status_code == 404


def test_cannot_delete_running_job(make_client):
    blocker = BlockingRun()
    client = make_client(blocker)
    job_id = client.post("/api/jobs", json=new_job_payload()).json()["id"]
    assert blocker.started.wait(5)

    res = client.delete(f"/api/jobs/{job_id}")
    assert res.status_code == 409
    blocker.release()
    wait_idle(client)
    assert client.delete(f"/api/jobs/{job_id}").status_code == 204


def test_deleting_a_queued_job_means_it_never_runs(make_client):
    blocker = BlockingRun()
    client = make_client(blocker)
    client.post("/api/jobs", json=new_job_payload(query="running"))
    assert blocker.started.wait(5)
    queued = client.post("/api/jobs", json=new_job_payload(query="queued")).json()["id"]

    assert client.delete(f"/api/jobs/{queued}").status_code == 204
    blocker.release()
    wait_idle(client)
    assert [job.query for job in blocker.calls] == ["running"]


# ---- misc --------------------------------------------------------------------


def test_cors_allows_the_vite_dev_server(make_client):
    client = make_client()
    res = client.options(
        "/api/jobs",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_docs_are_served(make_client):
    client = make_client()
    schema = client.get("/openapi.json").json()
    assert "/api/jobs" in schema["paths"]
    assert "/api/jobs/{job_id}/frame" in schema["paths"]
