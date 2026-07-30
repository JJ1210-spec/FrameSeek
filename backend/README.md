# FrameSeek — Backend (FastAPI + `frame_finder` pipeline)

```bash
# from the repo root, with the venv active
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --port 8000        # API docs: http://localhost:8000/docs
python -m pytest                        # tests
python -m frame_finder --help           # the pipeline as a CLI (docs/cli.md)
```

Requires **ffmpeg + ffprobe** on PATH. `GET /api/health` reports anything missing.

| Path | Purpose |
|------|---------|
| `app/main.py` | App factory; starts/stops the job worker in the lifespan |
| `app/api/` | Routers — `health.py`, `jobs.py` |
| `app/services/job_store.py` | Thread-safe job store, one folder per job under `data/jobs/` |
| `app/services/job_worker.py` | FIFO queue + single worker thread (pipeline config is global) |
| `app/services/pipeline_adapter.py` | Calls `frame_finder.configure()` + `run_pipeline(on_stage=…)` |
| `app/services/log_capture.py` | Routes the worker thread's `print()` output into the job log |
| `app/services/system_check.py` | ffmpeg / Python-package checks for `/api/health` |
| `frame_finder/` | The ML pipeline (download → VAD → Whisper → match → frame) |
| `tests/` | `api/`, `services/`, `pipeline/` — heavy ML stages are faked |

Environment variables: `DFF_DATA_DIR` (job storage, default `backend/data`),
`DFF_CORS_ORIGINS` (default `http://localhost:5173,http://127.0.0.1:5173`).
