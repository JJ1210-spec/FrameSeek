from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from ..schemas import Job, JobLogs, JobSummary, UrlJobCreate
from ..services.job_store import JobNotFound, JobStore
from ..services.job_worker import JobWorker
from .deps import get_store, get_worker

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job_or_404(store: JobStore, job_id: str) -> Job:
    try:
        return store.get(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")


@router.post("", response_model=Job, status_code=status.HTTP_201_CREATED)
def create_job(
    body: UrlJobCreate,
    store: JobStore = Depends(get_store),
    worker: JobWorker = Depends(get_worker),
) -> Job:
    """Queue a new search: find *query* in the video at *source_url*."""
    job = store.create(source_url=body.source_url, query=body.query, options=body.options)
    worker.submit(job.id)
    return store.get(job.id)


@router.get("", response_model=list[JobSummary])
def list_jobs(store: JobStore = Depends(get_store)) -> list[JobSummary]:
    return [
        JobSummary(
            id=job.id,
            status=job.status,
            source_url=job.source_url,
            query=job.query,
            created_at=job.created_at,
            finished_at=job.finished_at,
            result_status=(job.result or {}).get("status"),
            has_frame=job.has_frame,
        )
        for job in store.list_jobs()
    ]


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str, store: JobStore = Depends(get_store)) -> Job:
    return _get_job_or_404(store, job_id)


@router.get("/{job_id}/logs", response_model=JobLogs)
def get_job_logs(
    job_id: str,
    offset: int = Query(0, ge=0, description="Return lines from this absolute index onward"),
    store: JobStore = Depends(get_store),
) -> JobLogs:
    try:
        lines, total = store.logs(job_id, offset)
    except JobNotFound:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return JobLogs(id=job_id, lines=lines, total=total)


@router.get("/{job_id}/frame", response_class=FileResponse)
def get_job_frame(job_id: str, store: JobStore = Depends(get_store)):
    _get_job_or_404(store, job_id)
    frame = store.frame_path(job_id)
    if not frame.is_file():
        raise HTTPException(status_code=404, detail="No frame available for this job")
    return FileResponse(frame, media_type="image/jpeg", filename=f"{job_id}_frame.jpg")


@router.get("/{job_id}/video", response_class=FileResponse)
def get_job_video(job_id: str, store: JobStore = Depends(get_store)):
    job = _get_job_or_404(store, job_id)
    video = store.video_path(job_id)
    if job.status == "running" or video is None:
        raise HTTPException(status_code=404, detail="No video available for this job")
    return FileResponse(video)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, store: JobStore = Depends(get_store)) -> Response:
    job = _get_job_or_404(store, job_id)
    if job.status == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a job while it is running")
    store.delete(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
