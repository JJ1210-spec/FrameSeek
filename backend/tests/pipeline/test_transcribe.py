"""
Language handling and transcription arguments — the Whisper model is faked.
"""

import wave
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("faster_whisper")

from frame_finder import config, transcribe as tr  # noqa: E402
from frame_finder.audio import read_wav_windows  # noqa: E402


class FakeModel:
    def __init__(self, language=("en", 0.97), fail=False):
        self.language = language
        self.fail = fail
        self.transcribe_kwargs = None
        self.detect_calls = []

    def detect_language(self, audio, **kwargs):
        if self.fail:
            raise RuntimeError("model download failed")
        self.detect_calls.append((len(audio), kwargs))
        return self.language[0], self.language[1], []

    def transcribe(self, audio, **kwargs):
        self.transcribe_kwargs = kwargs
        seg = SimpleNamespace(text="hello", start=0.0, end=1.0, words=[])
        return iter([seg]), SimpleNamespace(language="en", language_probability=0.9)


@pytest.fixture
def fake_model(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(tr, "load_whisper_model", lambda size: model)
    return model


def write_wav(path, seconds, rate=16000):
    samples = (np.arange(int(seconds * rate)) % 1000).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return str(path)


# ---- model selection ----------------------------------------------------------


@pytest.mark.parametrize("model, language, expected", [
    ("tiny.en", "ta", "tiny"),
    ("base.en", "hi", "base"),
    ("small.en", "en", "small.en"),
    ("tiny.en", None, "tiny.en"),
    ("small", "ta", "small"),
    ("large-v3", "fr", "large-v3"),
])
def test_model_for_language(model, language, expected):
    assert tr.model_for_language(model, language) == expected


# ---- language detection ---------------------------------------------------------


def test_sample_starts_follow_speech_or_spread_over_video():
    segs = [{"start": s * 16000, "end": (s + 2) * 16000} for s in (5, 50, 100, 150, 200)]
    starts = tr.language_sample_starts(segs, 300.0)
    assert starts[0] == 4.0 and len(starts) == 4 and starts == sorted(starts)
    assert tr.language_sample_starts([], 200.0) == [20.0, 70.0, 120.0, 170.0]
    assert tr.language_sample_starts([], 0.0) == [0.0]


def test_read_wav_windows(tmp_path):
    path = write_wav(tmp_path / "a.wav", 10)
    audio = read_wav_windows(path, [0.0, 5.0, 9.5], window_sec=1.0)
    assert audio.dtype == np.float32
    assert len(audio) == 3 * 16000            # last window is clamped inside the file
    assert np.abs(audio).max() <= 1.0


def test_detect_language_uses_sampled_windows(tmp_path, fake_model):
    fake_model.language = ("ta", 0.8)
    path = write_wav(tmp_path / "a.wav", 200)
    result = tr.detect_language(path, [], 200.0)
    assert result["language"] == "ta" and result["source"] == "detected"
    samples, kwargs = fake_model.detect_calls[0]
    assert samples == 4 * 30 * 16000          # four 30 s windows, not the whole file
    assert kwargs["vad_filter"] is False


def test_unclear_language_falls_back_to_english(tmp_path, fake_model):
    fake_model.language = ("cy", 0.3)
    result = tr.detect_language(write_wav(tmp_path / "a.wav", 5), [], 5.0)
    assert result["language"] == "en" and result["detected"] == "cy"


def test_detection_errors_fall_back_to_english(tmp_path, fake_model):
    fake_model.fail = True
    result = tr.detect_language(write_wav(tmp_path / "a.wav", 5), [], 5.0)
    assert result == {"status": "ok", "language": "en", "probability": 0.0,
                      "source": "fallback", "_stage_duration_sec": result["_stage_duration_sec"]}


def test_forced_language_skips_detection(fake_model, monkeypatch):
    monkeypatch.setattr(config, "LANGUAGE", "hi")
    result = tr.detect_language("unused.wav")
    assert result["language"] == "hi" and result["source"] == "user"
    assert fake_model.detect_calls == []


# ---- transcribe() arguments --------------------------------------------------------


def test_speech_segments_become_clip_timestamps(fake_model):
    tr.transcribe("a.wav", "tiny.en", speech_segments=[{"start": 16000, "end": 48000}])
    kwargs = fake_model.transcribe_kwargs
    assert kwargs["clip_timestamps"] == [1.0, 3.0]
    assert kwargs["vad_filter"] is False
    assert kwargs["word_timestamps"] is True


def test_full_audio_mode_disables_vad(fake_model):
    tr.transcribe("a.wav", "tiny.en", vad_filter=False)
    assert fake_model.transcribe_kwargs["vad_filter"] is False
    assert "clip_timestamps" not in fake_model.transcribe_kwargs


def test_language_is_passed_to_multilingual_models_only(fake_model):
    tr.transcribe("a.wav", "tiny", language="ta")
    assert fake_model.transcribe_kwargs["language"] == "ta"
    tr.transcribe("a.wav", "tiny.en", language="ta")          # .en cannot take "ta"
    assert "language" not in fake_model.transcribe_kwargs
    tr.transcribe("a.wav", "tiny.en", language="en")
    assert fake_model.transcribe_kwargs["language"] == "en"
