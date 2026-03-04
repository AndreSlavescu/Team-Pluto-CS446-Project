from __future__ import annotations

import mimetypes
import re
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

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

_ID_PATTERN = re.compile(r"^[a-z]+_[0-9a-f]{16}$")

_rl_lock = threading.Lock()
_rl_buckets: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))

_RATE_LIMITS: Dict[str, tuple] = {
    "upload": (10, 60),
    "generation": (5, 60),
}


def _is_rate_limited(client_ip: str, bucket_name: str = "upload") -> bool:
    limit, window = _RATE_LIMITS.get(bucket_name, (10, 60))
    now = time.monotonic()
    cutoff = now - window
    with _rl_lock:
        entries = _rl_buckets[client_ip][bucket_name]
        _rl_buckets[client_ip][bucket_name] = [t for t in entries if t > cutoff]
        if len(_rl_buckets[client_ip][bucket_name]) >= limit:
            return True
        _rl_buckets[client_ip][bucket_name].append(now)
        return False


def _validate_id(value: str, prefix: str) -> None:
    if not _ID_PATTERN.match(value) or not value.startswith(f"{prefix}_"):
        _raise_http(400, "INVALID_ID", f"Invalid {prefix} identifier")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is required but not set"
        )
    yield


app = FastAPI(title="Pluto Generator API", version="0.1.0", lifespan=lifespan)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)


@app.get("/")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for deployment platforms."""
    return {"status": "healthy", "service": "pluto-backend"}


@app.get("/privacy-policy")
async def privacy_policy() -> HTMLResponse:
    """Privacy policy page for Google Play Store listing."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pluto - Privacy Policy</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 700px; margin: 0 auto; padding: 24px; line-height: 1.6;
         background: #0E0F12; color: #F4F7FF; }
  h1 { color: #3BD6C6; }
  h2 { color: #3BD6C6; font-size: 1.2em; margin-top: 1.5em; }
  a { color: #3BD6C6; }
</style>
</head>
<body>
<h1>Pluto Privacy Policy</h1>
<p><strong>Effective Date:</strong> March 2026</p>

<p>Pluto ("the App") is developed by Team Pluto as a university project at the
University of Waterloo.</p>

<h2>Data We Collect</h2>
<p>The App does not require you to create an account. We do not collect personal
information such as your name, email address, or location.</p>
<p>When you use the App, the following data is sent to our server solely to
generate your requested app:</p>
<ul>
  <li>The text prompt you enter describing the app you want to build</li>
  <li>Any images you optionally upload as reference</li>
</ul>
<p>This data is processed by our server using a third-party AI service (OpenAI)
to generate the app output. We do not store your prompts or images beyond what
is needed to complete the generation.</p>

<h2>Data Stored on Your Device</h2>
<p>Generated apps are saved locally on your device. This data never leaves your
device unless you choose to share it.</p>

<h2>Third-Party Services</h2>
<p>We use OpenAI's API to generate app content. Your prompts and uploaded images
are sent to OpenAI for processing. OpenAI's use of this data is governed by
their own privacy policy.</p>

<h2>Data Sharing</h2>
<p>We do not sell, trade, or share your data with any third parties beyond the
AI processing described above.</p>

<h2>Children's Privacy</h2>
<p>The App is not directed at children under 13. We do not knowingly collect
data from children.</p>

<h2>Changes to This Policy</h2>
<p>We may update this policy from time to time. Changes will be reflected in the
App and on this page.</p>

<h2>Contact</h2>
<p>If you have questions about this policy, contact us at
<a href="mailto:pluto-cs446@uwaterloo.ca">pluto-cs446@uwaterloo.ca</a>.</p>
</body>
</html>"""
    return HTMLResponse(
        content=html,
        headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


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
async def upload_file(request: Request, file: UploadFile = File(...)) -> UploadResponse:
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip, "upload"):
        _raise_http(429, "RATE_LIMITED", "Too many upload requests, please slow down")
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
    req: Request, request: CreateJobRequest, background_tasks: BackgroundTasks
) -> CreateJobResponse:
    client_ip = req.client.host if req.client else "unknown"
    if _is_rate_limited(client_ip, "generation"):
        _raise_http(429, "RATE_LIMITED", "Too many generation requests, please slow down")

    if len(request.prompt) > config.MAX_PROMPT_CHARS:
        _raise_http(400, "PROMPT_TOO_LONG", "Prompt exceeds maximum length")

    if len(request.input_images) > config.MAX_IMAGES:
        _raise_http(
            400, "TOO_MANY_IMAGES", "Too many images", {"max": config.MAX_IMAGES}
        )

    for upload_id in request.input_images:
        _validate_id(upload_id, "upl")
        if not store.get_upload(upload_id):
            _raise_http(400, "UNKNOWN_UPLOAD", "Upload not found")

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
    _validate_id(job_id, "job")
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
    _validate_id(app_id, "app")
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
    _validate_id(app_id, "app")
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
    _validate_id(job_id, "job")
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
    _validate_id(artifact_id, "art")
    artifact = store.get_artifact(artifact_id)
    if not artifact:
        _raise_http(404, "ARTIFACT_NOT_FOUND", "Artifact not found")

    path = Path(artifact["path"]).resolve()
    artifacts_dir = config.ARTIFACTS_DIR.resolve()
    try:
        path.relative_to(artifacts_dir)
    except ValueError:
        _raise_http(404, "ARTIFACT_NOT_FOUND", "Artifact not found")

    if not path.exists():
        _raise_http(404, "ARTIFACT_MISSING", "Artifact file missing")

    return FileResponse(path, filename=path.name, media_type="application/zip")
