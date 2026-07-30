import subprocess

from frame_finder import download
from frame_finder.download import _is_valid_video, acquire_video


def test_is_valid_video_rejects_missing_and_tiny_files(tmp_path):
    assert _is_valid_video(str(tmp_path / "missing.mp4")) is False
    tiny = tmp_path / "tiny.mp4"
    tiny.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    assert _is_valid_video(str(tiny)) is False


def test_is_valid_video_rejects_html_error_pages(tmp_path):
    page = tmp_path / "page.mp4"
    page.write_bytes(b"<!DOCTYPE html><html>" + b"x" * 200_000)
    assert _is_valid_video(str(page)) is False


def test_is_valid_video_accepts_mp4_and_mkv_headers(tmp_path):
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20_000)
    mkv = tmp_path / "a.mkv"
    mkv.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 20_000)
    assert _is_valid_video(str(mp4)) is True
    assert _is_valid_video(str(mkv)) is True


def test_local_file_source(tmp_path):
    video = tmp_path / "local.mp4"
    video.write_bytes(b"x")
    result = acquire_video(str(video), str(tmp_path / "out.mp4"))
    assert result["status"] == "ok"
    assert result["path"] == str(video)

    missing = acquire_video(str(tmp_path / "nope.mp4"), str(tmp_path / "out.mp4"))
    assert missing["status"] == "download_failed"
    assert "Local file not found" in missing["reason"]


def test_url_download_succeeds_via_ytdlp(tmp_path, monkeypatch):
    dest = tmp_path / "input_video.mp4"

    def fake_ytdlp(args):
        assert args[-1] == "https://example.com/v"
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20_000)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(download, "_run_ytdlp", fake_ytdlp)
    result = acquire_video("https://example.com/v", str(dest))
    assert result["status"] == "ok"
    assert result["path"] == str(dest)


def test_ytdlp_prefers_h264_at_most_1080p(tmp_path, monkeypatch):
    seen = []

    def fake_ytdlp(args):
        seen.append(args)
        (tmp_path / "input_video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20_000)

    monkeypatch.setattr(download, "_run_ytdlp", fake_ytdlp)
    acquire_video("https://example.com/v", str(tmp_path / "input_video.mp4"))

    fmt = seen[0][seen[0].index("-f") + 1]
    first_choice = fmt.split("/")[0]
    assert "vcodec^=avc1" in first_choice and "height<=1080" in first_choice
    assert fmt.endswith("/best")  # never refuses a video outright


def test_url_download_falls_back_to_curl_then_reports_failure(tmp_path, monkeypatch):
    def failing_ytdlp(args):
        raise subprocess.CalledProcessError(1, "yt-dlp", stderr="ERROR: Unsupported URL")

    curl_calls = []

    def failing_curl(url, dest):
        curl_calls.append(url)
        return {"status": "download_failed", "reason": "curl: (6) Could not resolve host"}

    monkeypatch.setattr(download, "_run_ytdlp", failing_ytdlp)
    monkeypatch.setattr(download, "_download_with_curl", failing_curl)

    result = acquire_video("https://example.invalid/v", str(tmp_path / "input_video.mp4"))
    assert curl_calls == ["https://example.invalid/v"]
    assert result["status"] == "download_failed"
    # both tools' errors are reported, one line each
    assert result["reason"].splitlines() == [
        "yt-dlp: yt-dlp (simple): ERROR: Unsupported URL",
        "curl: curl: (6) Could not resolve host",
    ]


def test_stale_invalid_file_is_removed_before_download(tmp_path, monkeypatch):
    dest = tmp_path / "input_video.mp4"
    dest.write_text("<html>old error page</html>")

    def fake_ytdlp(args):
        assert not dest.exists(), "stale file should be deleted first"
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20_000)

    monkeypatch.setattr(download, "_run_ytdlp", fake_ytdlp)
    assert acquire_video("https://example.com/v", str(dest))["status"] == "ok"
