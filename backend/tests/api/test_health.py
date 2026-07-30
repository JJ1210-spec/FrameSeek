from app.services import system_check


def test_health_reports_every_dependency(make_client):
    client = make_client()
    res = client.get("/api/health")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"
    names = [check["name"] for check in body["checks"]]
    assert any(name.startswith("ffmpeg") for name in names)
    assert any(name.startswith("ffprobe") for name in names)
    assert any(name.startswith("faster-whisper") for name in names)
    assert body["ready"] == all(check["ok"] for check in body["checks"])


def test_health_not_ready_when_ffmpeg_missing(make_client, monkeypatch):
    monkeypatch.setattr(system_check.shutil, "which", lambda name: None)
    client = make_client()

    body = client.get("/api/health").json()
    assert body["ready"] is False
    ffmpeg = next(c for c in body["checks"] if c["name"].startswith("ffmpeg"))
    assert ffmpeg["ok"] is False
    assert "winget install ffmpeg" in ffmpeg["detail"]


def test_health_ready_when_everything_present(make_client, monkeypatch):
    monkeypatch.setattr(system_check.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(system_check.importlib.util, "find_spec", lambda name: object())
    client = make_client()

    body = client.get("/api/health").json()
    assert body["ready"] is True
    assert all(check["ok"] for check in body["checks"])


def test_missing_python_module_is_reported():
    check = system_check.check_module("definitely_not_a_real_module_xyz", "fake")
    assert check.ok is False
    assert "pip install" in check.detail
