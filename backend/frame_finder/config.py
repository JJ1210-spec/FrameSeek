"""
Global configuration — shared mutable state for the pipeline.

All stage functions read from this module; ``main()`` writes to it once at
startup.  Modules import it as ``from . import config`` (or ``import config``
in the single-file variant) and access values as ``config.DEVICE`` etc.

Pattern: module-level variables are set by ``main.main()`` before any stage
runs.  No locks needed — the pipeline is single-threaded.
"""

# ---- device ---------------------------------------------------------------

DEVICE: str = "cpu"

# ---- paths ----------------------------------------------------------------

WORK_DIR: str = "./output"
VIDEO_PATH: str = ""
AUDIO_PATH: str = ""
AUDIO_SLICE_PATH: str = ""
FRAME_OUT_PATH: str = ""

# ---- thresholds -----------------------------------------------------------

MATCH_THRESHOLD: float = 80.0
COARSE_MATCH_THRESHOLD: float = 50.0
CANDIDATE_WINDOW_BUFFER_SEC: float = 45.0

# ---- tiering (seconds of *speech*) ----------------------------------------

SHORT_MAX_SEC: int = 180     # < 3 min  speech → "short"  tier
MEDIUM_MAX_SEC: int = 1200   # < 20 min speech → "medium" tier
                              # >= 20 min speech → "long"   tier

# ---- models ---------------------------------------------------------------

TIER_MODEL_MAP: dict = {}
LONG_COARSE_MODEL: str = "tiny.en"
LONG_FINE_MODEL: str = "tiny.en"
CPU_THREADS: int = 4

# Near-miss recovery: a larger model re-transcribes ±CANDIDATE_WINDOW_BUFFER_SEC
# around candidates that score between VERIFY_MIN_SCORE and MATCH_THRESHOLD
# (typical for singing or noisy audio, where the small model mishears words).
VERIFY_MODEL: str = "base.en"
# Only candidates scoring at least this are worth a verify pass (unrelated
# speech typically scores 50–60), and at most this many separate candidates
# are verified — repeated lines (song choruses) get a second chance.
VERIFY_MIN_SCORE: float = 65.0
VERIFY_MAX_CANDIDATES: int = 3

# ---- robustness -------------------------------------------------------------

# Silero VAD is tuned for clean speech; over music or singing it can report
# almost nothing.  Below this speech/duration ratio the VAD result is ignored
# and the full audio is transcribed.
MIN_SPEECH_COVERAGE: float = 0.10

# Spoken language: None = auto-detect with a small multilingual model.
# Non-English audio automatically switches ".en" models to multilingual ones.
LANGUAGE: str = None
LANGUAGE_DETECT_MODEL: str = "tiny"
LANGUAGE_MIN_PROBABILITY: float = 0.5

# ---- cookies (yt-dlp) -----------------------------------------------------

COOKIES_FROM_BROWSER: str = None
COOKIES_FILE: str = None

# ---- per-session caches (populated at runtime, never serialised) -----------

_MODEL_CACHE: dict = {}
_VAD_CACHE: dict = {}
