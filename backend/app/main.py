from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import config
from .generator import run_generation_job
from .models import (
    ApiError,
    AppManifest,
    AppVersionResponse,
    AppVersionsResponse,
    Artifact,
    CancelJobResponse,
    CreateJobRequest,
    CreateJobResponse,
    JobLog,
    JobProgress,
    JobStatusResponse,
    UploadResponse,
)
from .store import store

app = FastAPI(title="Pluto Generator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for deployment platforms."""
    return {"status": "healthy", "service": "pluto-backend"}


def _iso_to_dt(value: str) -> datetime:
    return store.parse_iso(value)


def _raise_http(
    status: int, code: str, message: str, details: Dict[str, Any] | None = None
) -> None:
    raise HTTPException(
        status_code=status,
        detail=ApiError(code=code, message=message, details=details).model_dump(
            by_alias=True
        ),
    )


def _download_url(artifact_id: str) -> str:
    base = config.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/v1/artifacts/{artifact_id}/download"


def _artifact_response(artifact_record: Dict[str, Any]) -> Artifact:
    path = Path(artifact_record["path"])
    sha256 = ""
    if path.exists():
        sha256 = _sha256(path)
    return Artifact(
        type=artifact_record["type"],
        download_url=_download_url(artifact_record["artifactId"]),
        expires_at=_iso_to_dt(artifact_record["expiresAt"]),
        sha256=sha256,
    )


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.post("/v1/uploads", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read()
    if len(content) > config.MAX_IMAGE_BYTES:
        _raise_http(400, "IMAGE_TOO_LARGE", "Image exceeds size limit")

    mime_type = (
        file.content_type
        or mimetypes.guess_type(file.filename or "")[0]
        or "application/octet-stream"
    )
    if not mime_type.startswith("image/"):
        _raise_http(400, "UNSUPPORTED_MEDIA_TYPE", "Only image uploads are supported")
    record = store.create_upload(
        content=content, filename=file.filename or "upload", mime_type=mime_type
    )
    return UploadResponse(
        upload_id=record["uploadId"],
        mime_type=record["mimeType"],
        size_bytes=record["sizeBytes"],
    )


@app.post("/v1/generation-jobs", response_model=CreateJobResponse)
async def create_generation_job(
    request: CreateJobRequest, background_tasks: BackgroundTasks
) -> CreateJobResponse:
    if len(request.prompt) > config.MAX_PROMPT_CHARS:
        _raise_http(400, "PROMPT_TOO_LONG", "Prompt exceeds maximum length")

    if len(request.input_images) > config.MAX_IMAGES:
        _raise_http(
            400, "TOO_MANY_IMAGES", "Too many images", {"max": config.MAX_IMAGES}
        )

    for upload_id in request.input_images:
        if not store.get_upload(upload_id):
            _raise_http(400, "UNKNOWN_UPLOAD", f"Upload not found: {upload_id}")

    app_record = store.create_app()
    job_record = store.create_job(
        app_id=app_record["appId"], request=request.model_dump(by_alias=True)
    )

    background_tasks.add_task(run_generation_job, store, job_record["jobId"])

    return CreateJobResponse(
        job_id=job_record["jobId"],
        app_id=job_record["appId"],
        status=job_record["status"],
        created_at=_iso_to_dt(job_record["createdAt"]),
    )


@app.get("/v1/generation-jobs/{job_id}", response_model=JobStatusResponse)
async def get_generation_job(job_id: str) -> JobStatusResponse:
    job = store.get_job(job_id)
    if not job:
        _raise_http(404, "JOB_NOT_FOUND", "Generation job not found")

    progress = None
    if job.get("progress"):
        progress = JobProgress(**job["progress"])

    logs = [
        JobLog(ts=_iso_to_dt(entry["ts"]), level=entry["level"], msg=entry["msg"])
        for entry in job.get("logs", [])
    ]

    error = None
    if job.get("error"):
        error = ApiError(**job["error"])

    return JobStatusResponse(
        job_id=job["jobId"],
        app_id=job["appId"],
        status=job["status"],
        created_at=_iso_to_dt(job["createdAt"]),
        updated_at=_iso_to_dt(job["updatedAt"]),
        progress=progress,
        logs=logs,
        error=error,
    )


@app.get("/v1/apps/{app_id}/versions/latest", response_model=AppVersionResponse)
async def get_latest_version(app_id: str) -> AppVersionResponse:
    app_record = store.get_app(app_id)
    if not app_record:
        _raise_http(404, "APP_NOT_FOUND", "App not found")

    version_id = app_record.get("latestVersionId")
    if not version_id:
        _raise_http(404, "VERSION_NOT_FOUND", "No versions available")

    version = store.get_version(version_id)
    if not version:
        _raise_http(404, "VERSION_NOT_FOUND", "Version not found")

    artifacts = []
    for artifact_id in version["artifactIds"]:
        artifact_record = store.get_artifact(artifact_id)
        if not artifact_record:
            _raise_http(404, "ARTIFACT_NOT_FOUND", "Artifact not found")
        artifacts.append(_artifact_response(artifact_record))
    manifest = AppManifest(
        display_name=version["manifest"].get("displayName"),
        package_name=version["manifest"].get("packageName"),
        features=version["manifest"].get("features", []),
        ui=version["manifest"].get("ui"),
    )

    return AppVersionResponse(
        version_id=version["versionId"],
        job_id=version["jobId"],
        created_at=_iso_to_dt(version["createdAt"]),
        artifacts=artifacts,
        manifest=manifest,
    )


@app.get("/v1/apps/{app_id}/versions", response_model=AppVersionsResponse)
async def list_versions(app_id: str, limit: int = 20) -> AppVersionsResponse:
    app_record = store.get_app(app_id)
    if not app_record:
        _raise_http(404, "APP_NOT_FOUND", "App not found")

    versions = store.list_versions(app_id)
    versions = versions[-limit:]

    responses: List[AppVersionResponse] = []
    for version in versions:
        artifacts = []
        for artifact_id in version["artifactIds"]:
            artifact_record = store.get_artifact(artifact_id)
            if not artifact_record:
                _raise_http(404, "ARTIFACT_NOT_FOUND", "Artifact not found")
            artifacts.append(_artifact_response(artifact_record))
        manifest = AppManifest(
            display_name=version["manifest"].get("displayName"),
            package_name=version["manifest"].get("packageName"),
            features=version["manifest"].get("features", []),
            ui=version["manifest"].get("ui"),
        )
        responses.append(
            AppVersionResponse(
                version_id=version["versionId"],
                job_id=version["jobId"],
                created_at=_iso_to_dt(version["createdAt"]),
                artifacts=artifacts,
                manifest=manifest,
            )
        )

    return AppVersionsResponse(app_id=app_id, versions=responses)


@app.post("/v1/generation-jobs/{job_id}/cancel", response_model=CancelJobResponse)
async def cancel_job(job_id: str) -> CancelJobResponse:
    job = store.get_job(job_id)
    if not job:
        _raise_http(404, "JOB_NOT_FOUND", "Generation job not found")

    if job["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        return CancelJobResponse(
            job_id=job_id, status=job["status"], updated_at=_iso_to_dt(job["updatedAt"])
        )

    store.request_cancel(job_id)
    store.update_job(job_id, {"status": "CANCELLED"})

    updated = store.get_job(job_id)
    return CancelJobResponse(
        job_id=job_id,
        status=updated["status"],
        updated_at=_iso_to_dt(updated["updatedAt"]),
    )


@app.get("/v1/artifacts/{artifact_id}/download")
async def download_artifact(artifact_id: str) -> FileResponse:
    artifact = store.get_artifact(artifact_id)
    if not artifact:
        _raise_http(404, "ARTIFACT_NOT_FOUND", "Artifact not found")

    path = Path(artifact["path"])
    if not path.exists():
        _raise_http(404, "ARTIFACT_MISSING", "Artifact file missing")

    return FileResponse(path, filename=path.name, media_type="application/zip")
