"""
Pipeline Orchestrator
=====================
Guard-clause chain — short-circuits on the first hard stage failure.
Every stage's wall-clock duration is collected in ``timings``.

Search strategy (CPU-first, escalates only when needed):

1. **Primary pass** — short/medium videos decode only the speech Silero VAD
   found; long videos use the coarse → ±45 s fine pass.  When VAD finds
   (almost) no speech — music, singing, loud soundtracks — the full audio is
   decoded instead.
2. **Full-audio retry** — if a VAD-gated pass missed the line, decode every
   second of audio (VAD often drops speech over music).
3. **Verify** — near-miss candidates (score between VERIFY_MIN_SCORE and the
   match threshold) are re-transcribed ±45 s with a larger model; up to three
   separate candidates, so a repeated line (a chorus) gets a second chance.

Language is auto-detected; non-English audio switches ``.en`` models to
their multilingual counterparts.
"""

import time
from typing import Callable, Optional

from . import config
from .download import acquire_video
from .metadata import get_video_metadata
from .audio import extract_audio, extract_audio_slice
from .vad import run_vad, classify_tier
from .transcribe import detect_language, model_for_language, transcribe
from .matching import match_dialogue
from .frame import extract_frame

FOUND = ("success", "partial_match")

LANGUAGE_NAMES = {
    "en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu", "ml": "Malayalam",
    "kn": "Kannada", "bn": "Bengali", "mr": "Marathi", "ur": "Urdu", "es": "Spanish",
    "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese", "ru": "Russian",
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "tr": "Turkish",
}


def _found(match: Optional[dict]) -> bool:
    return bool(match) and match.get("status") in FOUND


def _rank(match: Optional[dict]) -> tuple:
    if not match or match.get("similarity_score") is None:
        return (-1, -1.0)
    return (1 if _found(match) else 0, float(match["similarity_score"]))


def run_pipeline(
    video_url_or_path: str,
    target_dialogue: str,
    on_stage: Optional[Callable[[str], None]] = None,
) -> dict:
    """Run the full pipeline end to end.

    *on_stage*, if given, is called with each stage name just before that
    stage starts (used by the web backend for live progress).
    """
    pipeline_start = time.perf_counter()
    timings: dict = {}
    passes: list = []

    def enter(stage_name: str):
        if on_stage is not None:
            on_stage(stage_name)

    def record(stage_name: str, stage_result: dict):
        timings[stage_name] = stage_result.pop("_stage_duration_sec", None)

    def finish() -> None:
        timings["total"] = round(time.perf_counter() - pipeline_start, 3)

    # --- Stage 1: Video acquisition ---
    enter("acquire_video")
    video_result = acquire_video(video_url_or_path, config.VIDEO_PATH)
    record("acquire_video", video_result)
    if video_result["status"] != "ok":
        return {**video_result, "timings": timings}
    video_path = video_result["path"]

    # --- Stage 2: Metadata ---
    enter("get_video_metadata")
    metadata_result = get_video_metadata(video_path)
    record("get_video_metadata", metadata_result)
    if metadata_result["status"] != "ok":
        return {**metadata_result, "timings": timings}
    duration = metadata_result["duration_sec"] or 0.0

    # --- Stage 3: Audio extraction ---
    enter("extract_audio")
    audio_result = extract_audio(video_path, config.AUDIO_PATH)
    record("extract_audio", audio_result)
    if audio_result["status"] != "ok":
        return {**audio_result, "timings": timings}
    audio_path = audio_result["path"]

    # --- Stage 3b: VAD (advisory — never stops the pipeline) ---
    enter("run_vad")
    vad_result = run_vad(audio_path)
    record("run_vad", vad_result)
    if vad_result["status"] != "ok":
        print(f"[WARN] {vad_result.get('reason')}; transcribing the full audio instead")
        vad_result = {"status": "ok", "speech_segments": [], "total_speech_sec": 0.0}
    speech_sec = vad_result["total_speech_sec"]
    coverage = (speech_sec / duration) if duration else 0.0
    low_speech = coverage < config.MIN_SPEECH_COVERAGE

    # Tier by speech time — or by full duration when VAD cannot see the speech.
    tier_info = classify_tier(duration if low_speech else speech_sec)

    # --- Stage 3c: Language ---
    enter("detect_language")
    lang_result = detect_language(audio_path, vad_result["speech_segments"], duration)
    record("detect_language", lang_result)
    language = lang_result["language"]
    primary_model = model_for_language(tier_info["model_size"], language)

    print(
        f"[INFO] Tier: {tier_info['tier']}  |  model: {primary_model}  |  "
        f"language: {language} (p={lang_result.get('probability')})  |  "
        f"speech: {speech_sec}s of {round(duration, 1)}s ({coverage:.0%})"
        + ("  →  full-audio mode" if low_speech else "")
    )

    best: Optional[dict] = None
    last_error: Optional[dict] = None
    gated = False                 # did a pass skip audio because of VAD?
    long_coarse: Optional[dict] = None

    def consider(match: Optional[dict], offset: float = 0.0, note: str = None):
        nonlocal best
        if not match or match.get("similarity_score") is None:
            return
        candidate = dict(match)
        candidate["target_timestamp"] = (candidate.get("target_timestamp") or 0.0) + offset
        candidate["candidates"] = [
            {**c, "target_timestamp": c["target_timestamp"] + offset}
            for c in match.get("candidates") or []
        ]
        if note:
            candidate["note"] = note
        if _rank(candidate) > _rank(best):
            best = candidate

    def run_pass(stage_t, stage_m, audio, model, label, threshold=None, **kwargs):
        nonlocal last_error
        enter(stage_t)
        tr = transcribe(audio, model_size=model, language=language, **kwargs)
        record(stage_t, tr)
        passes.append(label)
        if tr["status"] != "ok":
            last_error = tr
            print(f"[WARN] {label}: {tr.get('reason')}")
            return None
        enter(stage_m)
        match = match_dialogue(tr["segments"], target_dialogue, threshold=threshold)
        record(stage_m, match)
        print(f"[INFO] {label}: {match['status']} (score {match.get('similarity_score')})")
        return match

    def window_around(t: float):
        start = max(0.0, t - config.CANDIDATE_WINDOW_BUFFER_SEC)
        end = min(duration or t + config.CANDIDATE_WINDOW_BUFFER_SEC,
                  t + config.CANDIDATE_WINDOW_BUFFER_SEC)
        return start, end

    def windowed_pass(prefix, candidate, model, label):
        """Slice ±buffer around *candidate* and re-match there."""
        nonlocal last_error
        start, end = window_around(candidate["target_timestamp"])
        slice_stage = "extract_audio_slice" if prefix == "fine" else f"extract_audio_slice_{prefix}"
        enter(slice_stage)
        sl = extract_audio_slice(audio_path, start, end, config.AUDIO_SLICE_PATH)
        record(slice_stage, sl)
        if sl["status"] != "ok":
            last_error = sl
            return None, 0.0
        match = run_pass(f"transcribe_{prefix}", f"match_dialogue_{prefix}",
                         sl["path"], model, label, vad_filter=False)
        return match, sl["window_start_sec"]

    # --- Stage 4+5: Primary pass ---
    if tier_info["tier"] != "long":
        if low_speech:
            match = run_pass("transcribe", "match_dialogue", audio_path, primary_model,
                             f"full audio · {primary_model}", vad_filter=False)
        else:
            gated = True
            match = run_pass("transcribe", "match_dialogue", audio_path, primary_model,
                             f"speech only · {primary_model}",
                             speech_segments=vad_result["speech_segments"])
        consider(match)
    else:
        # Long: coarse pass → candidate window → fine pass.
        # NOTE: the coarse pass uses faster-whisper's own vad_filter, not
        # clip_timestamps from Silero — constraining it to pre-computed windows
        # changes segment boundaries and can miss the target dialogue.
        coarse_model = model_for_language(config.LONG_COARSE_MODEL, language)
        gated = not low_speech
        long_coarse = run_pass(
            "transcribe_coarse", "match_dialogue_coarse", audio_path, coarse_model,
            f"coarse · {coarse_model}", threshold=config.COARSE_MATCH_THRESHOLD,
            vad_filter=not low_speech,
        )
        if long_coarse:
            consider({**long_coarse, "status": "no_match"})   # candidate only
        if _found(long_coarse):
            fine_model = model_for_language(config.LONG_FINE_MODEL, language)
            fine, offset = windowed_pass("fine", long_coarse, fine_model, f"fine ±45 s · {fine_model}")
            consider(fine, offset)

    # --- Recovery A: verify a near-miss with a larger model (cheap: ±45 s) ---
    verified_at = set()

    def try_verify():
        """Re-check the top separate near-miss candidates with a larger model,
        stopping early on an exact hit."""
        if _found(best) or best is None:
            return
        candidates = best.get("candidates") or [best]
        candidates = [c for c in candidates
                      if c["similarity_score"] >= config.VERIFY_MIN_SCORE]
        verify_model = model_for_language(config.VERIFY_MODEL, language)
        for candidate in candidates[: config.VERIFY_MAX_CANDIDATES]:
            key = round(candidate["target_timestamp"], 1)
            if key in verified_at:
                continue
            verified_at.add(key)
            verified, offset = windowed_pass(
                "verify", candidate, verify_model,
                f"verify ±45 s @ {candidate['target_timestamp']:.0f}s · {verify_model}",
            )
            if _found(verified):
                consider(verified, offset,
                         note=f"Confirmed by {verify_model} on a ±45 s window.")
                if best["similarity_score"] >= 100.0:
                    return

    try_verify()

    # --- Recovery B: full-audio retry when VAD may have hidden the line ---
    # (skipped for long videos whose coarse pass already located a candidate —
    #  a full no-VAD pass over an hour of audio costs minutes on a CPU)
    if not _found(best) and gated and not _found(long_coarse):
        model = (primary_model if tier_info["tier"] != "long"
                 else model_for_language(config.LONG_COARSE_MODEL, language))
        threshold = config.COARSE_MATCH_THRESHOLD if tier_info["tier"] == "long" else None
        full = run_pass("transcribe_full", "match_dialogue_full", audio_path, model,
                        f"full audio · {model}", threshold=threshold, vad_filter=False)
        if tier_info["tier"] == "long" and full:
            full = {**full, "status": "no_match"}          # long: a candidate to verify
        consider(full)
        try_verify()

    # Long videos: keep the old behaviour — a coarse candidate the fine and
    # verify passes could not confirm is still reported, flagged as low confidence.
    if not _found(best) and _found(long_coarse):
        best = {**long_coarse, "status": "partial_match",
                "note": "Fine-pass verification failed; using coarse-pass estimate (lower confidence)."}

    language_info = {
        "code": language,
        "name": LANGUAGE_NAMES.get(language, language),
        "probability": lang_result.get("probability"),
    }
    tier_details = {
        "tier": tier_info["tier"],
        "model_size": primary_model,
        "total_speech_sec": speech_sec,
        "speech_coverage": round(coverage, 3),
        "passes": passes,
    }

    # --- Nothing found ---
    if not _found(best):
        finish()
        if best is None and last_error is not None:
            return {**last_error, "query": target_dialogue, "language": language_info,
                    "tier_info": tier_details, "timings": timings}
        reason = (best or {}).get("reason") or "The line was not found in the transcript."
        if language != "en" and target_dialogue.isascii():
            reason += (f" The audio is {language_info['name']} — type the dialogue in that "
                       "language, as it is spoken.")
        return {
            "status": "no_match",
            "query": target_dialogue,
            "closest_text": (best or {}).get("matched_text"),
            "similarity_score": (best or {}).get("similarity_score"),
            "reason": reason,
            "language": language_info,
            "tier_info": tier_details,
            "timings": timings,
        }

    # --- Stage 6+7: Frame extraction ---
    enter("extract_frame")
    frame_result = extract_frame(
        video_path,
        best["target_timestamp"],
        metadata_result["fps"],
        config.FRAME_OUT_PATH,
    )
    record("extract_frame", frame_result)
    if frame_result["status"] != "ok":
        return {**frame_result, "timings": timings}

    finish()

    return {
        "status": best["status"],
        "query": target_dialogue,
        "matched_text": best["matched_text"],
        "similarity_score": best["similarity_score"],
        "timestamp_sec": round(best["target_timestamp"], 3),
        "note": best.get("note"),
        "frame_number": frame_result["frame_number"],
        "frame_image_path": frame_result["path"],
        "video_metadata": {
            "fps": metadata_result["fps"],
            "duration_sec": metadata_result["duration_sec"],
            "is_vfr": metadata_result["is_vfr"],
        },
        "language": language_info,
        "tier_info": tier_details,
        "timings": timings,
    }
