"""
Dependency checks for ``/api/health`` — cheap, no heavy imports.
"""

import importlib.util
import shutil

from ..schemas import DependencyCheck

PYTHON_MODULES = {
    "faster_whisper": "faster-whisper (speech-to-text)",
    "torch": "torch (Silero VAD)",
    "cv2": "opencv-python-headless (frames)",
    "rapidfuzz": "rapidfuzz (fuzzy matching)",
    "yt_dlp": "yt-dlp (URL downloads)",
}

SYSTEM_BINARIES = {
    "ffmpeg": "ffmpeg (audio extraction)",
    "ffprobe": "ffprobe (video metadata)",
}


def check_binary(name: str, label: str) -> DependencyCheck:
    path = shutil.which(name)
    if path:
        return DependencyCheck(name=label, ok=True, detail=path)
    return DependencyCheck(
        name=label, ok=False,
        detail=f"'{name}' not found on PATH — install ffmpeg (e.g. `winget install ffmpeg`) and restart the terminal",
    )


def check_module(module: str, label: str) -> DependencyCheck:
    try:
        found = importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        found = False
    if found:
        return DependencyCheck(name=label, ok=True, detail="installed")
    return DependencyCheck(
        name=label, ok=False,
        detail=f"Python module '{module}' missing — run `pip install -r backend/requirements.txt`",
    )


def run_checks() -> list[DependencyCheck]:
    checks = []
    checks += [check_binary(name, label) for name, label in SYSTEM_BINARIES.items()]
    checks += [check_module(module, label) for module, label in PYTHON_MODULES.items()]
    return checks
