"""
Pipeline orchestration with every stage faked — verifies the guard-clause
chain, tier routing, the robustness fallbacks (full-audio retry, near-miss
verification, language switching), coarse→fine offset math and on_stage.
"""

import pytest

pytest.importorskip("torch")
pytest.importorskip("faster_whisper")

from frame_finder import pipeline  # noqa: E402

from .conftest import segment  # noqa: E402

QUERY = "my mind rebels at stagnation"
HIT = "My mind rebels at stagnation"


class FakeTranscriber:
    """Returns scripted transcripts in call order and records every call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, audio, model_size, speech_segments=None, vad_filter=True, language=None):
        self.calls.append({
            "audio": audio, "model": model_size, "speech_segments": speech_segments,
            "vad_filter": vad_filter, "language": language,
        })
        response = self.responses[min(len(self.calls), len(self.responses)) - 1]
        return dict(response)


def ok(*segments):
    return {"status": "ok", "segments": list(segments)}


FAILED = {"status": "transcription_failed", "reason": "decoder crash"}


@pytest.fixture
def stages(monkeypatch):
    """Happy-path fakes for every stage (short tier, English, 50 % speech)."""

    def install(name, fn):
        monkeypatch.setattr(pipeline, name, fn)
        return fn

    install("acquire_video", lambda src, dest: {"status": "ok", "path": dest, "_stage_duration_sec": 1.0})
    install("get_video_metadata", lambda p: {
        "status": "ok", "fps": 25.0, "total_frames": 3000, "duration_sec": 120.0,
        "is_vfr": False, "_stage_duration_sec": 0.1,
    })
    install("extract_audio", lambda v, a: {"status": "ok", "path": a, "_stage_duration_sec": 2.0})
    install("run_vad", lambda a: {
        "status": "ok", "speech_segments": [{"start": 0, "end": 16000}],
        "total_speech_sec": 60.0, "_stage_duration_sec": 3.0,
    })
    install("detect_language", lambda a, segs=None, dur=0.0: {
        "status": "ok", "language": "en", "probability": 0.97, "_stage_duration_sec": 0.5,
    })
    install("transcribe", FakeTranscriber(ok(segment("hello there", 1.0), segment(HIT, 12.0))))
    install("extract_audio_slice", lambda a, s, e, o: {
        "status": "ok", "path": o, "window_start_sec": s, "_stage_duration_sec": 0.2,
    })
    install("extract_frame", lambda v, t, fps, out: {
        "status": "ok", "frame_number": round(t * fps), "path": out, "_stage_duration_sec": 0.1,
    })
    return install


# ---- happy path ----------------------------------------------------------------


def test_short_tier_success(stages):
    seen = []
    result = pipeline.run_pipeline("https://example.com/v", QUERY, on_stage=seen.append)

    assert result["status"] == "success"
    assert result["similarity_score"] == 100.0
    assert result["timestamp_sec"] == 12.0
    assert result["frame_number"] == 300
    assert result["tier_info"]["tier"] == "short"
    assert result["tier_info"]["model_size"] == "tiny.en"
    assert result["tier_info"]["speech_coverage"] == 0.5
    assert result["tier_info"]["passes"] == ["speech only · tiny.en"]
    assert result["language"] == {"code": "en", "name": "English", "probability": 0.97}
    assert result["video_metadata"] == {"fps": 25.0, "duration_sec": 120.0, "is_vfr": False}
    assert seen == [
        "acquire_video", "get_video_metadata", "extract_audio", "run_vad", "detect_language",
        "transcribe", "match_dialogue", "extract_frame",
    ]
    assert set(result["timings"]) == set(seen) | {"total"}


def test_speech_only_pass_uses_vad_segments(stages):
    fake = stages("transcribe", FakeTranscriber(ok(segment(HIT, 5.0))))
    pipeline.run_pipeline("x", QUERY)
    assert fake.calls[0]["speech_segments"] == [{"start": 0, "end": 16000}]
    assert fake.calls[0]["language"] == "en"


def test_on_stage_is_optional(stages):
    assert pipeline.run_pipeline("x", QUERY)["status"] == "success"


# ---- hard failures still short-circuit -----------------------------------------------


@pytest.mark.parametrize(
    "stage, failure",
    [
        ("acquire_video", {"status": "download_failed", "reason": "404"}),
        ("get_video_metadata", {"status": "metadata_failed", "reason": "bad fps"}),
        ("extract_audio", {"status": "no_audio_track", "reason": "silent"}),
        ("extract_frame", {"status": "frame_extraction_failed", "reason": "seek"}),
    ],
)
def test_hard_failures_short_circuit(stages, stage, failure):
    seen = []
    stages(stage, lambda *a, **k: dict(failure))
    result = pipeline.run_pipeline("x", QUERY, on_stage=seen.append)

    assert result["status"] == failure["status"]
    assert result["reason"] == failure["reason"]
    assert seen[-1] == stage
    assert "timings" in result


def test_transcription_failing_everywhere_is_reported(stages):
    fake = stages("transcribe", FakeTranscriber(FAILED))
    seen = []
    result = pipeline.run_pipeline("x", QUERY, on_stage=seen.append)

    assert result["status"] == "transcription_failed"
    assert result["reason"] == "decoder crash"
    assert [c["vad_filter"] for c in fake.calls] == [True, False]   # speech-only, then full audio
    assert seen[-1] == "transcribe_full"


# ---- robustness: VAD is advisory ----------------------------------------------------


def test_vad_failure_does_not_stop_the_pipeline(stages):
    stages("run_vad", lambda a: {"status": "transcription_failed", "reason": "VAD failed: offline"})
    fake = stages("transcribe", FakeTranscriber(ok(segment(HIT, 7.0))))
    result = pipeline.run_pipeline("x", QUERY)

    assert result["status"] == "success"
    assert fake.calls[0]["speech_segments"] is None
    assert fake.calls[0]["vad_filter"] is False
    assert result["tier_info"]["passes"] == ["full audio · tiny.en"]


def test_no_detected_speech_transcribes_full_audio(stages):
    """Songs / soundtracks: Silero finds ~nothing, Whisper still hears the line."""
    stages("run_vad", lambda a: {"status": "ok", "speech_segments": [], "total_speech_sec": 0.0})
    fake = stages("transcribe", FakeTranscriber(ok(segment(HIT, 42.0))))
    result = pipeline.run_pipeline("x", QUERY)

    assert result["status"] == "success"
    assert result["timestamp_sec"] == 42.0
    assert fake.calls == [{"audio": fake.calls[0]["audio"], "model": "tiny.en", "speech_segments": None,
                           "vad_filter": False, "language": "en"}]
    assert result["tier_info"]["speech_coverage"] == 0.0


def test_low_speech_coverage_tiers_by_duration(stages):
    # 6 s of "speech" in a 25-minute concert → long tier by duration
    stages("get_video_metadata", lambda p: {
        "status": "ok", "fps": 25.0, "total_frames": 1, "duration_sec": 1500.0, "is_vfr": False,
    })
    stages("run_vad", lambda a: {"status": "ok", "speech_segments": [{"start": 0, "end": 96000}],
                                 "total_speech_sec": 6.0})
    fake = stages("transcribe", FakeTranscriber(ok(segment(HIT, 600.0)), ok(segment(HIT, 45.0))))
    result = pipeline.run_pipeline("x", QUERY)

    assert result["tier_info"]["tier"] == "long"
    assert fake.calls[0]["vad_filter"] is False          # coarse pass over everything
    assert result["timestamp_sec"] == 600.0              # 555 + 45


def test_speech_only_miss_retries_full_audio(stages):
    fake = stages("transcribe", FakeTranscriber(
        ok(segment("nothing useful here", 1.0)),
        ok(segment("nothing useful here", 1.0), segment(HIT, 88.0)),
    ))
    seen = []
    result = pipeline.run_pipeline("x", QUERY, on_stage=seen.append)

    assert result["status"] == "success"
    assert result["timestamp_sec"] == 88.0
    assert fake.calls[1]["vad_filter"] is False and fake.calls[1]["speech_segments"] is None
    assert "transcribe_full" in seen and "match_dialogue_full" in seen
    assert result["tier_info"]["passes"] == ["speech only · tiny.en", "full audio · tiny.en"]


# ---- robustness: near-miss verification ---------------------------------------------


def test_near_miss_is_verified_with_larger_model(stages):
    """tiny.en mishears a sung line; base.en on ±45 s around it gets it right."""
    stages("run_vad", lambda a: {"status": "ok", "speech_segments": [], "total_speech_sec": 0.0})
    fake = stages("transcribe", FakeTranscriber(
        ok(segment("cause i'll not think it's true", 100.0)),        # tiny.en, full audio
        ok(segment("cause i'm not thinking straight", 45.0)),        # base.en, window
    ))
    stages("get_video_metadata", lambda p: {
        "status": "ok", "fps": 25.0, "total_frames": 1, "duration_sec": 315.0, "is_vfr": False,
    })
    seen = []
    result = pipeline.run_pipeline("x", "Cause I'm not thinking straight", on_stage=seen.append)

    assert result["status"] == "success"
    assert fake.calls[1]["model"] == "base.en"
    assert fake.calls[1]["vad_filter"] is False
    assert result["timestamp_sec"] == 100.0             # window 55 s + 45 s
    assert "Confirmed by base.en" in result["note"]
    assert "transcribe_verify" in seen


def test_repeated_line_verifies_the_next_candidate(stages):
    """Chorus: base.en mishears the first occurrence but gets the second one."""
    stages("run_vad", lambda a: {"status": "ok", "speech_segments": [], "total_speech_sec": 0.0})
    stages("get_video_metadata", lambda p: {
        "status": "ok", "fps": 25.0, "total_frames": 1, "duration_sec": 315.0, "is_vfr": False,
    })
    fake = stages("transcribe", FakeTranscriber(
        ok(segment("cause i won't think it's true", 105.0),
           segment("cause i'll not think it's true", 176.0)),        # tiny.en, full audio
        ok(segment("the pace cause im not big in train", 45.0)),      # base.en @105 — still wrong
        ok(segment("cause i'm not thinking straight", 45.0)),         # base.en @176 — exact
    ))
    result = pipeline.run_pipeline("x", "Cause I'm not thinking straight")

    assert result["status"] == "success"
    assert result["timestamp_sec"] == 176.0
    assert [c["model"] for c in fake.calls] == ["tiny.en", "base.en", "base.en"]
    assert len([p for p in result["tier_info"]["passes"] if p.startswith("verify")]) == 2


def test_low_scoring_candidates_are_not_verified(stages):
    """Unrelated speech scores ~50–60: not worth a (slow) verify pass."""
    stages("transcribe", FakeTranscriber(ok(segment("they cannot bang for the dam", 3.0))))
    fake_calls = pipeline.transcribe.calls
    result = pipeline.run_pipeline("x", "the eagle has landed at midnight")
    assert result["status"] == "no_match"
    assert all(call["model"] == "tiny.en" for call in fake_calls)


def test_hopeless_candidate_is_not_verified(stages):
    fake = stages("transcribe", FakeTranscriber(ok(segment("completely unrelated chatter", 1.0))))
    result = pipeline.run_pipeline("x", "the quick brown fox jumps over the lazy dog")

    assert result["status"] == "no_match"
    assert result["closest_text"] == "completely unrelated chatter"
    assert all(call["model"] == "tiny.en" for call in fake.calls)   # no base.en verify
    assert "frame_number" not in result


# ---- robustness: language ----------------------------------------------------------------


def test_non_english_audio_switches_to_multilingual_models(stages):
    stages("detect_language", lambda a, s=None, d=0.0: {"status": "ok", "language": "ta", "probability": 0.8})
    tamil = "நல்லா இரு போ"
    fake = stages("transcribe", FakeTranscriber(ok(segment(tamil, 30.0))))
    result = pipeline.run_pipeline("x", tamil)

    assert result["status"] == "success"
    assert fake.calls[0]["model"] == "tiny"
    assert fake.calls[0]["language"] == "ta"
    assert result["language"]["name"] == "Tamil"
    assert result["tier_info"]["model_size"] == "tiny"


def test_english_query_on_non_english_audio_explains_itself(stages):
    stages("detect_language", lambda a, s=None, d=0.0: {"status": "ok", "language": "ta", "probability": 0.65})
    stages("transcribe", FakeTranscriber(ok(segment("நல்லா இரு போ", 30.0))))
    result = pipeline.run_pipeline("x", "i am always angry")

    assert result["status"] == "no_match"
    assert "The audio is Tamil" in result["reason"]


# ---- long tier -----------------------------------------------------------------------


@pytest.fixture
def long_video(stages):
    stages("get_video_metadata", lambda p: {
        "status": "ok", "fps": 25.0, "total_frames": 90000, "duration_sec": 3600.0, "is_vfr": False,
    })
    stages("run_vad", lambda a: {"status": "ok", "speech_segments": [], "total_speech_sec": 1500.0})
    return stages


def test_long_tier_coarse_to_fine_adds_window_offset(long_video):
    fake = long_video("transcribe", FakeTranscriber(
        ok(segment("My mind rebels it's stagnation", 324.0)),
        ok(segment(HIT, 45.5)),
    ))
    seen = []
    result = pipeline.run_pipeline("x", QUERY, on_stage=seen.append)

    assert seen == [
        "acquire_video", "get_video_metadata", "extract_audio", "run_vad", "detect_language",
        "transcribe_coarse", "match_dialogue_coarse", "extract_audio_slice",
        "transcribe_fine", "match_dialogue_fine", "extract_frame",
    ]
    assert fake.calls[0]["vad_filter"] is True and fake.calls[0]["speech_segments"] is None
    assert fake.calls[1]["vad_filter"] is False
    # window starts at 324 - 45 = 279 → 279 + 45.5
    assert result["timestamp_sec"] == 324.5
    assert result["status"] == "success"
    assert result["tier_info"]["tier"] == "long"


def test_long_tier_unconfirmed_candidate_falls_back_to_coarse(long_video):
    fake = long_video("transcribe", FakeTranscriber(
        ok(segment("My mind rebels it's stagnation", 324.0)),
        FAILED,                                            # fine (tiny.en)
        FAILED,                                            # verify (base.en)
    ))
    seen = []
    result = pipeline.run_pipeline("x", QUERY, on_stage=seen.append)

    assert result["status"] == "partial_match"
    assert result["timestamp_sec"] == 324.0
    assert "lower confidence" in result["note"]
    assert [c["model"] for c in fake.calls] == ["tiny.en", "tiny.en", "base.en"]
    assert "transcribe_full" not in seen          # no hour-long full retry


def test_long_tier_coarse_no_match_tries_full_audio_then_stops(long_video):
    fake = long_video("transcribe", FakeTranscriber(ok(segment("zzz", 1.0))))
    seen = []
    result = pipeline.run_pipeline("x", QUERY, on_stage=seen.append)

    assert result["status"] == "no_match"
    assert result["tier_info"]["tier"] == "long"
    assert [c["vad_filter"] for c in fake.calls] == [True, False]
    assert seen[-1] == "match_dialogue_full"


def test_window_is_clamped_to_video_bounds(long_video):
    windows = []
    long_video("transcribe", FakeTranscriber(ok(segment(HIT, 10.0)), ok(segment(HIT, 1.0))))
    long_video("extract_audio_slice", lambda a, s, e, o: windows.append((s, e)) or {
        "status": "ok", "path": o, "window_start_sec": s,
    })
    pipeline.run_pipeline("x", QUERY)
    assert windows == [(0.0, 55.0)]
