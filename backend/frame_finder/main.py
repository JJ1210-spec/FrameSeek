"""
CLI + entry point
==================
Parse arguments, populate config, run the pipeline, save and print results.
"""

import os
import sys
import json
import argparse

import torch

from . import config
from .pipeline import run_pipeline


def parse_args():
    parser = argparse.ArgumentParser(
        prog="python -m frame_finder",
        description="Find the exact video frame for a spoken dialogue line.",
    )
    parser.add_argument(
        "--source", required=True,
        help="URL (yt-dlp supported) or local path to the video file.",
    )
    parser.add_argument(
        "--query", required=True,
        help="The dialogue line to search for (partial or full sentence).",
    )
    parser.add_argument(
        "--outdir", default="./output",
        help="Output directory (created automatically). Default: ./output",
    )
    parser.add_argument(
        "--model", default=None,
        help="Override the faster-whisper model for short/medium tier. "
             "Default: 'tiny.en' on CPU, 'large-v3' on GPU.",
    )
    parser.add_argument(
        "--coarse-model", default="tiny.en",
        help="Model for the long-tier coarse pass. Default: tiny.en",
    )
    parser.add_argument(
        "--fine-model", default="tiny.en",
        help="Model for the long-tier fine pass. Default: tiny.en",
    )
    parser.add_argument(
        "--verify-model", default="base.en",
        help="Larger model used to confirm near-miss matches on a ±45 s window. "
             "Default: base.en",
    )
    parser.add_argument(
        "--language", default=None,
        help="Spoken language code (e.g. en, ta, hi). Default: auto-detect.",
    )
    parser.add_argument(
        "--device", default=None,
        help="Compute device: 'cuda' or 'cpu'. Auto-detected if not set.",
    )
    parser.add_argument(
        "--cpu-threads", type=int, default=None,
        help="CPU threads for ctranslate2 (default: min(8, logical cores)).",
    )
    parser.add_argument(
        "--match-threshold", type=float, default=80.0,
        help="Rapidfuzz score threshold for fuzzy match. Default: 80.0",
    )
    parser.add_argument(
        "--coarse-threshold", type=float, default=50.0,
        help="Match threshold for the coarse pass. Default: 50.0",
    )
    parser.add_argument(
        "--window-buffer", type=float, default=45.0,
        help="Seconds of padding around the coarse timestamp. Default: 45.0",
    )
    parser.add_argument(
        "--cookies-from-browser", default=None, metavar="BROWSER",
        help="Extract cookies from browser (e.g. chrome, firefox, edge).",
    )
    parser.add_argument(
        "--cookies", default=None, metavar="FILE",
        help="Path to a Netscape-format cookies.txt file.",
    )
    return parser.parse_args()


def configure(
    outdir: str = "./output",
    model: str = None,
    coarse_model: str = "tiny.en",
    fine_model: str = "tiny.en",
    verify_model: str = "base.en",
    language: str = None,
    device: str = None,
    cpu_threads: int = None,
    match_threshold: float = 80.0,
    coarse_threshold: float = 50.0,
    window_buffer: float = 45.0,
    cookies_from_browser: str = None,
    cookies: str = None,
) -> None:
    """Populate the shared config.  Used by the CLI and the web backend."""
    config.COOKIES_FROM_BROWSER = cookies_from_browser
    config.COOKIES_FILE = cookies

    if device:
        config.DEVICE = device
    else:
        config.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    config.CPU_THREADS = cpu_threads or min(8, os.cpu_count() or 4)
    thread_note = f" (threads: {config.CPU_THREADS})" if config.DEVICE == "cpu" else ""
    print(f"[INFO] Using device: {config.DEVICE}{thread_note}")

    default_model = "tiny.en" if config.DEVICE == "cpu" else "large-v3"
    user_model = model or default_model

    config.TIER_MODEL_MAP = {
        "short":  user_model,
        "medium": user_model,
        "long":   user_model,
    }
    config.LONG_COARSE_MODEL = coarse_model
    config.LONG_FINE_MODEL   = fine_model
    config.VERIFY_MODEL      = verify_model
    config.LANGUAGE          = (language or "").strip().lower() or None

    config.WORK_DIR         = os.path.abspath(outdir)
    os.makedirs(config.WORK_DIR, exist_ok=True)
    config.VIDEO_PATH       = os.path.join(config.WORK_DIR, "input_video.mp4")
    config.AUDIO_PATH       = os.path.join(config.WORK_DIR, "audio.wav")
    config.AUDIO_SLICE_PATH = os.path.join(config.WORK_DIR, "audio_candidate_slice.wav")
    config.FRAME_OUT_PATH   = os.path.join(config.WORK_DIR, "matched_frame.jpg")

    config.MATCH_THRESHOLD        = match_threshold
    config.COARSE_MATCH_THRESHOLD = coarse_threshold
    config.CANDIDATE_WINDOW_BUFFER_SEC = window_buffer


def main():
    args = parse_args()

    # --- Populate the shared config ---
    configure(
        outdir=args.outdir,
        model=args.model,
        coarse_model=args.coarse_model,
        fine_model=args.fine_model,
        verify_model=args.verify_model,
        language=args.language,
        device=args.device,
        cpu_threads=args.cpu_threads,
        match_threshold=args.match_threshold,
        coarse_threshold=args.coarse_threshold,
        window_buffer=args.window_buffer,
        cookies_from_browser=args.cookies_from_browser,
        cookies=args.cookies,
    )

    # --- Run ---
    print(f"[INFO] Query  : {args.query}")
    print(f"[INFO] Source : {args.source}")
    print(f"[INFO] Output : {config.WORK_DIR}")
    print()

    result = run_pipeline(args.source, args.query)

    clean = {k: v for k, v in result.items() if v is not None}
    print()
    print(json.dumps(clean, indent=2))

    result_json_path = os.path.join(config.WORK_DIR, "result.json")
    with open(result_json_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    print(f"\n[INFO] Result saved  : {result_json_path}")

    if result.get("frame_image_path") and os.path.exists(result["frame_image_path"]):
        print(f"[INFO] Frame image   : {result['frame_image_path']}")

    return 0 if result.get("status") in ("success", "partial_match") else 1
