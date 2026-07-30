"""
Frame extraction against a real (synthetic) video written with OpenCV.
Each frame's brightness encodes its index so we can verify the exact frame.
"""

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from frame_finder.frame import extract_frame  # noqa: E402

FPS = 10.0
N_FRAMES = 30


@pytest.fixture(scope="module")
def synthetic_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "synthetic.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (64, 48))
    assert writer.isOpened()
    for i in range(N_FRAMES):
        writer.write(np.full((48, 64, 3), i * 8, dtype=np.uint8))
    writer.release()
    return str(path)


@pytest.mark.parametrize("timestamp, expected_frame", [(0.0, 0), (1.0, 10), (1.24, 12), (1.26, 13), (2.9, 29)])
def test_extracts_the_exact_frame(synthetic_video, tmp_path, timestamp, expected_frame):
    out = tmp_path / "frame.jpg"
    result = extract_frame(synthetic_video, timestamp, FPS, str(out))

    assert result["status"] == "ok"
    assert result["frame_number"] == expected_frame
    assert result["path"] == str(out)
    image = cv2.imread(str(out))
    assert image.shape == (48, 64, 3)
    assert abs(float(image.mean()) - expected_frame * 8) < 4  # JPEG tolerance


def test_timestamp_past_end_fails_cleanly(synthetic_video, tmp_path):
    result = extract_frame(synthetic_video, 60.0, FPS, str(tmp_path / "frame.jpg"))
    assert result["status"] == "frame_extraction_failed"
    assert "600" in result["reason"]


def test_unreadable_video_fails_cleanly(tmp_path):
    result = extract_frame(str(tmp_path / "missing.mp4"), 1.0, FPS, str(tmp_path / "f.jpg"))
    assert result["status"] == "frame_extraction_failed"
