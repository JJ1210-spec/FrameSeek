# FrameSeek pipeline (`frame_finder`) — internals & CLI reference

`backend/frame_finder/` is the ML pipeline behind the web app. It can also be run
on its own from the command line — useful for batch jobs and benchmarking.

```bash
cd backend
python -m frame_finder \
    --source "https://ok.ru/video/248244667877" \
    --query  "My mind rebels at stagnation" \
    --outdir ./output
```

Result (example):

```json
{
  "status": "partial_match",
  "query": "My mind rebels at stagnation",
  "matched_text": "My mind rebels, it's stagnation, give me problems, give me work, give me the most",
  "similarity_score": 78.9,
  "timestamp_sec": 324.77,
  "frame_number": 7787,
  "frame_image_path": "output/matched_frame.jpg"
}
```

## How it works

```
Video URL
    │
    ▼
yt-dlp (H.264 ≤1080p) / curl ─► MP4      (curl --tls-max 1.2 fallback)
    │
    ▼
ffprobe ─────────────────────► FPS · duration · VFR flag
    │
    ▼
ffmpeg ──────────────────────► mono 16 kHz WAV
    │
    ▼
Silero VAD ──────────────────► speech segments · total speech seconds
    │
    ▼
Tier classifier ─────────────► short (<3 min speech) / medium (<20 min) / long
    │                           │
    │  short/medium:            └─ long: coarse pass (tiny.en, full audio)
    │  single pass                  → candidate window (±45 s)
    │                               → fine pass (tiny.en, window only)
    ▼
Dialogue matcher (exact substring → rapidfuzz token_sort_ratio fallback)
    │
    ▼
OpenCV frame seek ───────────► matched_frame.jpg  +  result.json
```

The coarse pass only has to locate the right ±45 s window; the fine pass
re-transcribes just that window for word-level precision — so a small model
delivers large-model accuracy at a fraction of the cost.

## Robustness: music, singing and other languages

Silero VAD is tuned for clean speech. Over a soundtrack or in a song it can
report almost nothing (a 5-minute pop song: 6 s of "speech"; a Tamil film
song: 0 s). The pipeline therefore treats VAD as **advice, not a gate**:

| Situation | What happens |
|-----------|--------------|
| VAD speech < 10 % of the video | Skip VAD clipping — transcribe the **full audio**; tier by duration |
| VAD fails to load (e.g. offline) | Same — full audio |
| Speech-only pass misses the line | **Full-audio retry** without VAD |
| Best candidate scores 50–79 (near miss) | **Verify**: re-transcribe ±45 s around it with `--verify-model` (`base.en`) |
| Audio is not English | `tiny.en` → `tiny`, `base.en` → `base`, … with the detected language pinned |
| English query, non-English audio, no match | The `reason` says which language was heard |

Every result records the detected `language` and the `tier_info.passes` that ran,
e.g. `["full audio · tiny.en", "verify ±45 s · base.en"]`. Extra passes run
**only on a miss**, so clean speech costs the same as before.

## Modules

| Module | Stage |
|--------|-------|
| `config.py` | Shared settings (device, paths, thresholds, model caches) |
| `timing.py` | `@timed` decorator — per-stage wall-clock timings |
| `download.py` | Video acquisition: yt-dlp → curl TLS 1.2 fallback, HTML-page rejection |
| `metadata.py` | OpenCV + ffprobe: fps, duration, VFR flag |
| `audio.py` | ffmpeg audio extraction + stdlib WAV reader for VAD |
| `vad.py` | Silero VAD (advisory) + tier classification |
| `transcribe.py` | faster-whisper model cache, language detection, transcription (`clip_timestamps` fix) |
| `matching.py` | Word-stream matcher: exact run of words, then a rapidfuzz sliding window; word-level timestamps; Unicode + contraction normalisation |
| `frame.py` | OpenCV frame seek + JPEG export |
| `pipeline.py` | Orchestrator — guard-clause chain, optional `on_stage` progress hook |
| `main.py` | `configure()` (shared with the web API) + argparse CLI |

## CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | *(required)* | Video URL (anything yt-dlp supports) |
| `--query`  | *(required)* | Dialogue line to search for |
| `--outdir` | `./output`  | Output directory (created if absent) |
| `--model`  | `tiny.en` (CPU) / `large-v3` (GPU) | Whisper model for short/medium tier |
| `--coarse-model` | `tiny.en` | Model for the long-tier coarse pass |
| `--fine-model`   | `tiny.en` | Model for the long-tier fine pass |
| `--verify-model` | `base.en` | Larger model that confirms near-miss matches on a ±45 s window |
| `--language` | auto | Spoken language code (`en`, `ta`, `hi`, …); `.en` models switch to multilingual automatically for non-English audio |
| `--device` | auto | `cpu` or `cuda` |
| `--cpu-threads` | `min(8, logical cores)` | CPU threads for faster-whisper |
| `--match-threshold` | `80.0` | Fuzzy match acceptance score (0–100) |
| `--coarse-threshold`| `50.0` | Fuzzy match score for the coarse pass |
| `--window-buffer`   | `45.0` | Seconds of padding around the coarse timestamp |
| `--cookies-from-browser` | — | Browser cookies for login-gated videos (`chrome`, `firefox`, `edge`) |
| `--cookies`              | — | Netscape-format cookies.txt file |

Every flag except `--source/--query/--outdir/--device/--cookies` is also exposed
in the web UI under **Advanced options**.

## Output

```
output/
├── matched_frame.jpg   ← the exact video frame
└── result.json         ← full structured result (+ per-stage timings)
```

Statuses: `success` (exact match) · `partial_match` (fuzzy ≥ threshold) ·
`no_match` (line not found — `closest_text` included) · stage failures
(`download_failed`, `metadata_failed`, `no_audio_track`,
`audio_extraction_failed`, `transcription_failed`, `frame_extraction_failed`)
with a `reason`.

## Performance

Measured on an **Intel i5-1245U laptop (CPU only)**, 54.4-minute video,
query *"My mind rebels at stagnation"*:

| Configuration | Total runtime | Match result |
|---|---|---|
| original (`small`, beam 5) | est. 45–70 min | — |
| `base.en` variant | 15.8–20.9 min | fuzzy 61.2 → frame @ 326.15 s |
| **`tiny.en` + coarse-to-fine (default)** | **5.4 min** | **`partial_match` 78.9 → frame 7787 @ 324.77 s** |

Ground truth (GPU `large-v3`): frame 7785 @ 324.68 s — Δ 2 frames (0.08 s).
Short clips (≈ 24 s of speech) finish in ≈ 33 s end-to-end.

## Troubleshooting

- **First run is slow** — the Whisper model (~75 MB for `tiny.en`) and Silero VAD
  are downloaded once, then cached.
- **ok.ru / SSL connection reset (Error 10054)** — handled by the curl
  `--tls-max 1.2` fallback. If every method fails the job reports
  `download_failed` with the reason.
- **`SSL: self-signed certificate in certificate chain`** — antivirus/proxy HTTPS
  interception; try another network.
- **`WinError 1314`** on first model download — Windows symlink permission in the
  HuggingFace cache. Delete `~/.cache/huggingface/hub/models--Systran--faster-whisper-<model>`
  and retry (or enable Developer Mode).
- **Non-English content** — use a multilingual model (`--model small`); `.en`
  models are English-only.
- Run-to-run times vary ±30 % on laptop CPUs (thermal throttling).
