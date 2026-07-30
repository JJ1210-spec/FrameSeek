from types import SimpleNamespace

import pytest

from frame_finder import config


def word(text, start, end=None):
    return SimpleNamespace(word=text, start=start, end=end if end is not None else start + 0.3)


def segment(text, start, end=None, words=None):
    """A stand-in for faster-whisper's Segment (text/start/end/words)."""
    if words is None:
        words, t = [], start
        for token in text.split():
            words.append(word(" " + token, t))
            t += 0.4
    return SimpleNamespace(text=text, start=start, end=end if end is not None else start + 3, words=words)


@pytest.fixture(autouse=True)
def reset_config(tmp_path):
    """Give every test a clean, predictable config."""
    saved = {k: getattr(config, k) for k in dir(config) if k.isupper() or k.startswith("_") and not k.startswith("__")}
    config.DEVICE = "cpu"
    config.MATCH_THRESHOLD = 80.0
    config.COARSE_MATCH_THRESHOLD = 50.0
    config.CANDIDATE_WINDOW_BUFFER_SEC = 45.0
    config.TIER_MODEL_MAP = {"short": "tiny.en", "medium": "tiny.en", "long": "tiny.en"}
    config.LONG_COARSE_MODEL = "tiny.en"
    config.LONG_FINE_MODEL = "tiny.en"
    config.WORK_DIR = str(tmp_path)
    config.VIDEO_PATH = str(tmp_path / "input_video.mp4")
    config.AUDIO_PATH = str(tmp_path / "audio.wav")
    config.AUDIO_SLICE_PATH = str(tmp_path / "audio_candidate_slice.wav")
    config.FRAME_OUT_PATH = str(tmp_path / "matched_frame.jpg")
    yield
    for key, value in saved.items():
        setattr(config, key, value)
