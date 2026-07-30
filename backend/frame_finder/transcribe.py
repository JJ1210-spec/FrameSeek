"""
Stage 4 — Language detection + Transcription
=============================================
Load faster-whisper models (cached), detect the spoken language, and
transcribe with word-level timestamps.  The clip_timestamps bug fix lives here.
"""

from faster_whisper import WhisperModel

from . import config
from .timing import timed


def load_whisper_model(model_size: str) -> WhisperModel:
    """Load (or reuse) a faster-whisper model.  int8 on CPU, float16 on CUDA."""
    if model_size not in config._MODEL_CACHE:
        compute = "float16" if config.DEVICE == "cuda" else "int8"
        print(f"[INFO] Loading faster-whisper '{model_size}' on {config.DEVICE} ({compute}) ...")
        kwargs = {"cpu_threads": config.CPU_THREADS} if config.DEVICE == "cpu" else {}
        config._MODEL_CACHE[model_size] = WhisperModel(
            model_size, device=config.DEVICE, compute_type=compute, **kwargs
        )
    else:
        print(f"[INFO] Reusing cached faster-whisper '{model_size}'")
    return config._MODEL_CACHE[model_size]


def model_for_language(model_size: str, language: str = None) -> str:
    """English-only ``.en`` models cannot transcribe other languages — swap them
    for the multilingual model of the same size (``tiny.en`` → ``tiny``)."""
    if language and language != "en" and model_size.endswith(".en"):
        return model_size[: -len(".en")]
    return model_size


def language_sample_starts(speech_segments, duration_sec: float, count: int = 4) -> list:
    """Where to sample audio for language detection: spread over detected
    speech when there is any, otherwise evenly over the whole video."""
    if speech_segments:
        picks = [
            speech_segments[round(i * (len(speech_segments) - 1) / max(count - 1, 1))]
            for i in range(count)
        ]
        starts = sorted({max(0.0, seg["start"] / 16000 - 1.0) for seg in picks})
    else:
        starts = [duration_sec * f for f in (0.1, 0.35, 0.6, 0.85)] if duration_sec else [0.0]
    return starts


@timed
def detect_language(audio_path: str, speech_segments=None, duration_sec: float = 0.0) -> dict:
    """Detect the spoken language with a small multilingual model.

    Never fails the pipeline: on any error it falls back to English.
    """
    if config.LANGUAGE:
        return {"status": "ok", "language": config.LANGUAGE, "probability": 1.0, "source": "user"}
    try:
        from .audio import read_wav_windows

        model = load_whisper_model(config.LANGUAGE_DETECT_MODEL)
        starts = language_sample_starts(speech_segments, duration_sec)
        audio = read_wav_windows(audio_path, starts, window_sec=30.0)
        language, probability, _ = model.detect_language(
            audio, vad_filter=False, language_detection_segments=len(starts)
        )
        if probability < config.LANGUAGE_MIN_PROBABILITY:
            print(f"[INFO] Language unclear ({language} p={probability:.2f}); assuming English")
            return {"status": "ok", "language": "en", "probability": round(probability, 3),
                    "source": "fallback", "detected": language}
        return {"status": "ok", "language": language, "probability": round(probability, 3),
                "source": "detected"}
    except Exception as e:
        print(f"[WARN] Language detection failed ({e}); assuming English")
        return {"status": "ok", "language": "en", "probability": 0.0, "source": "fallback"}


@timed
def transcribe(
    audio_path: str,
    model_size: str = "tiny.en",
    speech_segments=None,
    vad_filter: bool = True,
    language: str = None,
) -> dict:
    """
    Transcribe audio with word-level timestamps.

    * speech_segments (from Silero VAD) → passed as clip_timestamps, so only
      speech is decoded and faster-whisper's internal VAD is skipped.
    * otherwise ``vad_filter`` decides whether faster-whisper's own VAD runs.
      ``vad_filter=False`` decodes every second of audio — slower, but it is
      the only way to catch speech buried in music or singing.
    * ``language`` pins the decoding language (None = model default).

    BUG FIX: faster-whisper's clip_timestamps default is ``"0"`` (a string),
    not ``None``.  Passing ``None`` explicitly crashes ``generate_segments``
    with ``'NoneType' object is not iterable``.  We only pass it when we
    actually have VAD segments; otherwise the library default applies.
    """
    try:
        model = load_whisper_model(model_size)

        clip_timestamps = None
        if speech_segments:
            clip_timestamps = []
            for seg in speech_segments:
                clip_timestamps.extend([seg["start"] / 16000, seg["end"] / 16000])

        # Only include clip_timestamps when non-None to avoid the bug.
        transcribe_kwargs = dict(
            word_timestamps=True,
            vad_filter=bool(vad_filter) and clip_timestamps is None,
            beam_size=5,
            condition_on_previous_text=False,
        )
        if clip_timestamps is not None:
            transcribe_kwargs["clip_timestamps"] = clip_timestamps
        if language and not (model_size.endswith(".en") and language != "en"):
            transcribe_kwargs["language"] = language

        segments_gen, info = model.transcribe(audio_path, **transcribe_kwargs)

        # Consume the lazy generator with per-segment safety so one corrupt
        # segment is skipped instead of aborting the whole transcription.
        segments = []
        for seg in segments_gen:
            try:
                _ = seg.words  # materialise; surfaces any latent error early
                segments.append(seg)
            except Exception:
                continue

        if not segments:
            return {"status": "transcription_failed", "reason": "No speech detected in audio"}

        return {
            "status": "ok",
            "segments": segments,
            "language": info.language,
            "language_probability": info.language_probability,
        }
    except Exception as e:
        return {"status": "transcription_failed", "reason": str(e)}
