import time

import pytest

from frame_finder import config
from frame_finder.timing import timed


def test_timed_injects_duration_into_dict_results():
    @timed
    def stage():
        time.sleep(0.01)
        return {"status": "ok"}

    result = stage()
    assert result["status"] == "ok"
    assert result["_stage_duration_sec"] >= 0.01


def test_timed_passes_non_dict_results_through():
    @timed
    def stage(x):
        return x * 2

    assert stage(21) == 42
    assert stage.__name__ == "stage"


class TestClassifyTier:
    @pytest.fixture(autouse=True)
    def _vad(self):
        pytest.importorskip("torch")
        from frame_finder.vad import classify_tier

        self.classify = classify_tier
        config.TIER_MODEL_MAP = {"short": "tiny.en", "medium": "base.en", "long": "small.en"}

    @pytest.mark.parametrize(
        "speech_sec, tier, model",
        [
            (0, "short", "tiny.en"),
            (179.99, "short", "tiny.en"),
            (180, "medium", "base.en"),
            (1199.99, "medium", "base.en"),
            (1200, "long", "small.en"),
            (3600, "long", "small.en"),
        ],
    )
    def test_boundaries(self, speech_sec, tier, model):
        assert self.classify(speech_sec) == {"tier": tier, "model_size": model}
