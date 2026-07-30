import pytest

pytest.importorskip("rapidfuzz")

from frame_finder import config  # noqa: E402
from frame_finder.matching import match_dialogue  # noqa: E402

from .conftest import segment, word  # noqa: E402

TRANSCRIPT = [
    segment("Good morning, Watson.", 10.0),
    segment("My mind rebels at stagnation. Give me problems.", 324.0,
            words=[word(" My", 324.68), word(" mind", 324.9), word(" rebels", 325.1),
                   word(" at", 325.5), word(" stagnation.", 325.7), word(" Give", 326.5),
                   word(" me", 326.7), word(" problems.", 326.9)]),
    segment("The game is afoot.", 900.0),
]


def test_exact_match_uses_word_level_start_time():
    result = match_dialogue(TRANSCRIPT, "my mind rebels")
    assert result["status"] == "success"
    assert result["similarity_score"] == 100.0
    assert result["matched_text"] == "My mind rebels at stagnation. Give me problems."
    assert result["target_timestamp"] == 324.68


def test_exact_match_mid_segment_points_at_first_query_word():
    result = match_dialogue(TRANSCRIPT, "Give me problems")
    assert result["status"] == "success"
    assert result["target_timestamp"] == 326.5


def test_exact_match_is_case_and_whitespace_insensitive():
    result = match_dialogue(TRANSCRIPT, "   THE GAME IS AFOOT   ")
    assert result["status"] == "success"
    assert result["target_timestamp"] == 900.0


def test_fuzzy_match_above_threshold_is_partial_match():
    # Whisper heard "it's" instead of "at" — the real-world case from approach.md
    segments = [segment("My mind rebels, it's stagnation, give me problems", 324.77)]
    result = match_dialogue(segments, "My mind rebels at stagnation give me problems")
    assert result["status"] == "partial_match"
    assert 80 <= result["similarity_score"] < 100
    assert result["target_timestamp"] == 324.77


def test_fuzzy_match_below_threshold_is_no_match_with_closest_text():
    result = match_dialogue(TRANSCRIPT, "I am the one who knocks")
    assert result["status"] == "no_match"
    assert result["similarity_score"] < 80
    # the closest window's segment(s) are reported for debugging
    assert any(seg.text in result["matched_text"] for seg in TRANSCRIPT)


def test_explicit_threshold_overrides_config():
    segments = [segment("my mind rebels its stagnation", 5.0)]
    query = "my mind rebels at stagnation today"
    strict = match_dialogue(segments, query, threshold=99)
    lenient = match_dialogue(segments, query, threshold=10)
    assert strict["status"] == "no_match"
    assert lenient["status"] == "partial_match"
    assert strict["similarity_score"] == lenient["similarity_score"]


def test_default_threshold_comes_from_config():
    segments = [segment("my mind rebels its stagnation", 5.0)]
    query = "my mind rebels at stagnation today"
    config.MATCH_THRESHOLD = 10
    assert match_dialogue(segments, query)["status"] == "partial_match"
    config.MATCH_THRESHOLD = 99
    assert match_dialogue(segments, query)["status"] == "no_match"


def test_no_segments_is_no_match():
    result = match_dialogue([], "anything")
    assert result["status"] == "no_match"
    assert result["reason"] == "No segments available to compare"


def test_segment_without_words_interpolates_word_time():
    # 4 tokens spread over 42.0–45.0 s → "my" (2nd token) starts at 42.75 s
    segments = [segment("Elementary my dear Watson", 42.0, end=45.0, words=None)]
    segments[0].words = None
    result = match_dialogue(segments, "my dear watson")
    assert result["status"] == "success"
    assert result["target_timestamp"] == pytest.approx(42.75)
    assert match_dialogue(segments, "elementary my dear")["target_timestamp"] == 42.0


def test_none_word_objects_are_skipped():
    words = [None, word(" Elementary", 1.0), word(" my", 1.4), word(" dear", 1.6), word(" Watson", 1.9)]
    segments = [segment("Elementary my dear Watson", 0.5, words=words)]
    result = match_dialogue(segments, "elementary my dear")
    assert result["status"] == "success"
    assert result["target_timestamp"] == 1.0


def test_none_segment_text_does_not_crash():
    segments = [segment("", 0.0, words=[]), segment("hello world", 3.0)]
    segments[0].text = None
    result = match_dialogue(segments, "hello world")
    assert result["status"] == "success"
    assert result["target_timestamp"] == 3.0


def test_timing_is_injected():
    assert "_stage_duration_sec" in match_dialogue(TRANSCRIPT, "watson")


# ---- word-stream matching ---------------------------------------------------


def test_contractions_and_punctuation_are_normalised():
    segments = [segment("I'm always angry.", 60.32)]
    result = match_dialogue(segments, "i am always angry")
    assert result["status"] == "success"
    assert result["similarity_score"] == 100.0
    assert result["target_timestamp"] == 60.32


def test_line_spanning_two_segments_is_found():
    segments = [
        segment("Give me problems,", 10.0, words=[word(" Give", 10.0), word(" me", 10.3), word(" problems,", 10.5)]),
        segment("give me work.", 11.2, words=[word(" give", 11.2), word(" me", 11.5), word(" work.", 11.7)]),
    ]
    result = match_dialogue(segments, "problems give me work")
    assert result["status"] == "success"
    assert result["target_timestamp"] == 10.5
    assert result["matched_text"] == "Give me problems, give me work."


def test_fuzzy_match_uses_word_level_timestamp():
    # Whisper mishears one word in a long segment; the timestamp must point
    # at the first matched word, not the start of the segment.
    words = [word(" Well,", 100.0), word(" as", 100.4), word(" I", 100.6), word(" said,", 100.8),
             word(" my", 101.5), word(" mind", 101.7), word(" rebels", 102.0),
             word(" it's", 102.4), word(" stagnation.", 102.6)]
    segments = [segment("Well, as I said, my mind rebels it's stagnation.", 100.0, words=words)]
    result = match_dialogue(segments, "My mind rebels at stagnation")
    assert result["status"] == "partial_match"
    assert result["similarity_score"] >= 80
    assert result["target_timestamp"] == 101.5


def test_non_latin_scripts_are_kept():
    tamil = "நல்லா இரு போ"
    segments = [segment("ஏதோ ஒரு வரி", 3.0), segment(f"{tamil}!", 20.0)]
    result = match_dialogue(segments, tamil)
    assert result["status"] == "success"
    assert result["target_timestamp"] == 20.0


def test_first_occurrence_wins_on_ties():
    segments = [segment("love me like you do", 57.0), segment("love me like you do", 121.0)]
    assert match_dialogue(segments, "love me like you do")["target_timestamp"] == 57.0


def test_query_of_only_punctuation_is_rejected():
    result = match_dialogue([segment("hello", 1.0)], "?!...")
    assert result["status"] == "no_match"
    assert "empty" in result["reason"]


def test_candidates_are_separate_near_misses():
    segments = [
        segment("cause i won't think it's true", 105.0),
        segment("something else entirely here", 130.0),
        segment("cause i'll not think it's true", 176.0),
    ]
    result = match_dialogue(segments, "cause i'm not thinking straight")
    times = [c["target_timestamp"] for c in result["candidates"]]
    assert 105.0 in times and 176.0 in times
    # candidates are ordered by score and at least one verify-window apart
    scores = [c["similarity_score"] for c in result["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert all(abs(a - b) >= config.CANDIDATE_WINDOW_BUFFER_SEC
               for i, a in enumerate(times) for b in times[i + 1:])
