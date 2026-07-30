"""
Stage 5 — Dialogue Matching
=============================
Word-level matching across the whole transcript:

  1. Exact — the normalised query appears as a contiguous run of words
     (score 100.0).
  2. Fuzzy — every window of roughly the query's length is scored with
     rapidfuzz ``ratio``; the best window wins.

Both passes work on the flattened word stream, so a line that straddles two
Whisper segments is still found, and the timestamp is always the start of the
first matched *word* (not the start of the segment).

Normalisation is Unicode-aware (punctuation and symbols are dropped, letters
and combining marks of every script are kept) and expands common English
contractions, so "I am always angry" matches "I'm always angry."
"""

import re
import unicodedata

from rapidfuzz import fuzz

from . import config
from .timing import timed

# Longer / shorter windows than the query are also scored, so an extra or
# missing word in the transcript does not sink the match.
WINDOW_SLACK = 2

_CONTRACTIONS = [
    (re.compile(r"\bcan't\b"), "can not"),
    (re.compile(r"\bwon't\b"), "will not"),
    (re.compile(r"\bshan't\b"), "shall not"),
    (re.compile(r"n't\b"), " not"),
    (re.compile(r"'re\b"), " are"),
    (re.compile(r"\bi'm\b"), "i am"),
    (re.compile(r"'ll\b"), " will"),
    (re.compile(r"'ve\b"), " have"),
]


def normalize_text(text: str) -> str:
    """Lower-case, expand contractions, drop punctuation/symbols, squash spaces."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    for pattern, replacement in _CONTRACTIONS:
        text = pattern.sub(replacement, text)
    cleaned = "".join(
        " " if unicodedata.category(ch)[0] in ("P", "S") else ch for ch in text
    )
    return " ".join(cleaned.split())


def _word_stream(segments) -> list:
    """Flatten segments into [(token, start, segment_index)] (one entry per token)."""
    stream = []
    for seg_index, seg in enumerate(segments):
        words = [w for w in (getattr(seg, "words", None) or []) if w is not None]
        timed_words = [
            (getattr(w, "word", None), getattr(w, "start", None)) for w in words
        ]
        timed_words = [(text, start) for text, start in timed_words if text]

        if not timed_words:
            # No word timestamps: spread the segment's tokens over its span.
            tokens = normalize_text(getattr(seg, "text", "")).split()
            seg_start = getattr(seg, "start", 0.0) or 0.0
            seg_end = getattr(seg, "end", seg_start) or seg_start
            step = (seg_end - seg_start) / max(len(tokens), 1)
            for i, token in enumerate(tokens):
                # First token keeps the exact segment start.
                stream.append((token, seg_start + i * step, seg_index))
            continue

        for text, start in timed_words:
            if start is None:
                start = getattr(seg, "start", 0.0) or 0.0
            # One Whisper "word" can normalise to several tokens ("I'm" → "i am").
            for token in normalize_text(text).split():
                stream.append((token, start, seg_index))
    return stream


def _segments_text(segments, first: int, last: int) -> str:
    return " ".join(
        (getattr(segments[i], "text", "") or "").strip() for i in range(first, last + 1)
    ).strip()


@timed
def match_dialogue(segments, target_text: str, threshold: float = None) -> dict:
    """
    Match *target_text* against transcribed segments.

    Returns a dict with ``status`` in ``{"success", "partial_match", "no_match"}``,
    ``matched_text`` (the transcript segment(s) containing the match),
    ``similarity_score`` (0–100) and ``target_timestamp`` (seconds, start of the
    first matched word).
    """
    if threshold is None:
        threshold = config.MATCH_THRESHOLD

    stream = _word_stream(segments or [])
    if not stream:
        return {"status": "no_match", "reason": "No segments available to compare"}

    query_tokens = normalize_text(target_text).split()
    if not query_tokens:
        return {"status": "no_match", "reason": "The dialogue query is empty after normalisation"}

    tokens = [token for token, _, _ in stream]
    n, q = len(tokens), len(query_tokens)
    query_str = " ".join(query_tokens)

    def result(status, score, start_idx, end_idx):
        first_seg, last_seg = stream[start_idx][2], stream[end_idx][2]
        return {
            "status": status,
            "matched_text": _segments_text(segments, first_seg, last_seg),
            "similarity_score": round(float(score), 2),
            "target_timestamp": stream[start_idx][1],
        }

    # --- Pass 1: exact contiguous word match ---
    for i in range(n - q + 1):
        if tokens[i:i + q] == query_tokens:
            return result("success", 100.0, i, i + q - 1)

    # --- Pass 2: fuzzy sliding window ---
    # best (score, end index) for every start index
    best_at = {}
    for size in range(max(1, q - WINDOW_SLACK), q + WINDOW_SLACK + 1):
        for i in range(0, max(n - size, 0) + 1):
            score = fuzz.ratio(query_str, " ".join(tokens[i:i + size]))
            if score > best_at.get(i, (-1.0, 0))[0]:
                best_at[i] = (score, min(i + size, n) - 1)

    # Highest score wins; the earliest occurrence wins a tie.
    start = max(best_at, key=lambda i: (best_at[i][0], -i))
    best_score, end = best_at[start]

    status = "partial_match" if best_score >= threshold else "no_match"
    matched = result(status, best_score, start, end)
    matched["candidates"] = _top_candidates(best_at, stream)
    return matched


def _top_candidates(best_at: dict, stream: list, limit: int = 3) -> list:
    """The best-scoring windows that are at least one verify-window apart, so a
    repeated line (e.g. a chorus) yields several places worth re-checking."""
    min_gap = config.CANDIDATE_WINDOW_BUFFER_SEC
    ranked = sorted(best_at.items(), key=lambda kv: (-kv[1][0], kv[0]))
    picked = []
    for i, (score, _) in ranked:
        t = stream[i][1]
        if all(abs(t - p["target_timestamp"]) >= min_gap for p in picked):
            picked.append({"target_timestamp": t, "similarity_score": round(float(score), 2)})
            if len(picked) == limit:
                break
    return picked
