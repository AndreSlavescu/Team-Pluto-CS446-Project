from __future__ import annotations

import logging
import mimetypes
import re
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from . import config
from . import database as db
from .auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_optional_user,
    hash_password,
    hash_token,
    verify_password,
)
from .appdb_routes import router as appdb_router
from .generator import run_generation_job
from .models import (
    ApiError,
    AppManifest,
    AppSummary,
    AppVersionResponse,
    AppVersionsResponse,
    Artifact,
    CancelJobResponse,
    CreateJobRequest,
    CreateJobResponse,
    DiscoverAppsResponse,
    JobLog,
    JobProgress,
    JobStatusResponse,
    LoginRequest,
    MyAppsResponse,
    PublishResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UploadResponse,
    UserResponse,
)
from .store import store

_ID_PATTERN = re.compile(r"^[a-z]+_[0-9a-f]{16}$")

_rl_lock = threading.Lock()
_rl_buckets: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))

_RATE_LIMITS: Dict[str, tuple] = {
    "upload": (10, 60),
    "generation": (5, 60),
    "auth": (10, 60),
    "db": (60, 60),
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
    if not config.JWT_SECRET:
        raise RuntimeError("JWT_SECRET environment variable is required but not set")
    db.init_db()
    yield


app = FastAPI(title="Pluto Generator API", version="0.1.0", lifespan=lifespan)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(self), geolocation=()"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.include_router(appdb_router)
_WEBVIEW_ORIGIN = "https://plutoapp.local"
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS + [_WEBVIEW_ORIGIN],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)

logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
            }
        },
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
<p>When you create an account, we collect your email address and a securely
hashed version of your password. We do not collect your name, location, or
other personal information.</p>
<p>When you use the App, the following data is sent to our server solely to
generate your requested app:</p>
<ul>
  <li>The text prompt you enter describing the app you want to build</li>
  <li>Any images you optionally upload as reference</li>
</ul>
<p>This data is processed by our server using a third-party AI service (OpenAI)
to generate the app output. Your prompts and uploaded images may be retained on
our server for a limited period to support generation and debugging.</p>

<h2>Account Deletion</h2>
<p>You can delete your account at any time from within the App. When you delete
your account, your email, password hash, and authentication tokens are
permanently removed from our servers.</p>

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


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _issue_tokens(user_id: str, email: str) -> TokenResponse:
    access = create_access_token(user_id, email)
    refresh = create_refresh_token()
    expires_at = (
        datetime.now() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    ).isoformat()
    db.create_refresh_token(
        user_id=user_id,
        token_hash=hash_token(refresh),
        expires_at=expires_at,
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/v1/auth/register", response_model=TokenResponse)
async def register(request: Request, body: RegisterRequest) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip, "auth"):
        _raise_http(429, "RATE_LIMITED", "Too many requests, please slow down")

    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        _raise_http(400, "INVALID_EMAIL", "Invalid email address")
    if len(body.password) < 8:
        _raise_http(400, "WEAK_PASSWORD", "Password must be at least 8 characters")
    if db.get_user_by_email(email):
        _raise_http(409, "EMAIL_TAKEN", "An account with this email already exists")

    hashed = hash_password(body.password)
    user = db.create_user(email=email, hashed_password=hashed)
    return _issue_tokens(user["userId"], user["email"])


@app.post("/v1/auth/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip, "auth"):
        _raise_http(429, "RATE_LIMITED", "Too many requests, please slow down")

    email = body.email.strip().lower()
    user = db.get_user_by_email(email)
    if not user or not verify_password(body.password, user["hashedPassword"]):
        _raise_http(401, "INVALID_CREDENTIALS", "Invalid email or password")

    return _issue_tokens(user["userId"], user["email"])


@app.post("/v1/auth/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    token_record = db.get_refresh_token_by_hash(hash_token(body.refresh_token))
    if not token_record:
        _raise_http(401, "INVALID_TOKEN", "Invalid refresh token")

    user = db.get_user(token_record["userId"])
    if not user:
        _raise_http(401, "INVALID_TOKEN", "User not found")

    db.delete_refresh_token(token_record["tokenId"])
    return _issue_tokens(user["userId"], user["email"])


@app.post("/v1/auth/logout")
async def logout(
    body: RefreshRequest,
    user: dict = Depends(get_current_user),
) -> Dict[str, str]:
    token_record = db.get_refresh_token_by_hash(hash_token(body.refresh_token))
    if token_record:
        db.delete_refresh_token(token_record["tokenId"])
    return {"status": "ok"}


@app.get("/v1/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        user_id=user["userId"],
        email=user["email"],
        created_at=_iso_to_dt(user["createdAt"]),
    )


@app.delete("/v1/auth/account")
async def delete_account(
    user: dict = Depends(get_current_user),
) -> Dict[str, str]:
    db.delete_refresh_tokens_for_user(user["userId"])
    db.delete_user(user["userId"])
    return {"status": "deleted"}


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


@app.get("/v1/my-apps", response_model=MyAppsResponse)
async def list_my_apps(
    user: dict = Depends(get_current_user),
) -> MyAppsResponse:
    apps = store.list_apps_by_owner(user["userId"])
    summaries: List[AppSummary] = []
    for app_record in apps:
        app_id = app_record["appId"]
        display_name = app_id
        features: List[str] = []
        updated_at = _iso_to_dt(app_record["createdAt"])

        version_id = app_record.get("latestVersionId")
        if version_id:
            version = store.get_version(version_id)
            if version:
                manifest = version.get("manifest", {})
                resolved = manifest.get("displayName", "")
                if resolved:
                    display_name = resolved
                features = manifest.get("features", [])
                updated_at = _iso_to_dt(version["createdAt"])

        summaries.append(
            AppSummary(
                app_id=app_id,
                display_name=display_name,
                created_at=_iso_to_dt(app_record["createdAt"]),
                updated_at=updated_at,
                features=features,
                published=app_record.get("published", False),
            )
        )

    summaries.sort(key=lambda s: s.updated_at or s.created_at, reverse=True)
    return MyAppsResponse(apps=summaries)


@app.post("/v1/apps/{app_id}/publish", response_model=PublishResponse)
async def publish_app(
    app_id: str,
    user: dict = Depends(get_current_user),
) -> PublishResponse:
    _validate_id(app_id, "app")
    app_record = store.get_app(app_id)
    if not app_record:
        _raise_http(404, "APP_NOT_FOUND", "App not found")
    if app_record.get("ownerId") != user["userId"]:
        _raise_http(403, "FORBIDDEN", "You can only publish your own apps")
    if not app_record.get("latestVersionId"):
        _raise_http(
            400, "NO_VERSION", "App must have at least one version before publishing"
        )

    store.set_app_published(app_id, True)
    return PublishResponse(app_id=app_id, published=True)


@app.post("/v1/apps/{app_id}/unpublish", response_model=PublishResponse)
async def unpublish_app(
    app_id: str,
    user: dict = Depends(get_current_user),
) -> PublishResponse:
    _validate_id(app_id, "app")
    app_record = store.get_app(app_id)
    if not app_record:
        _raise_http(404, "APP_NOT_FOUND", "App not found")
    if app_record.get("ownerId") != user["userId"]:
        _raise_http(403, "FORBIDDEN", "You can only unpublish your own apps")

    store.set_app_published(app_id, False)
    return PublishResponse(app_id=app_id, published=False)


@app.get("/v1/discover", response_model=DiscoverAppsResponse)
async def discover_apps() -> DiscoverAppsResponse:
    apps = store.list_published_apps()
    summaries: List[AppSummary] = []
    for app_record in apps:
        app_id = app_record["appId"]
        display_name = app_id
        features: List[str] = []
        updated_at = _iso_to_dt(app_record["createdAt"])

        version_id = app_record.get("latestVersionId")
        if version_id:
            version = store.get_version(version_id)
            if version:
                manifest = version.get("manifest", {})
                resolved = manifest.get("displayName", "")
                if resolved:
                    display_name = resolved
                features = manifest.get("features", [])
                updated_at = _iso_to_dt(version["createdAt"])

        author_email: str | None = None
        owner_id = app_record.get("ownerId")
        if owner_id:
            owner = db.get_user(owner_id)
            if owner:
                email = owner.get("email", "")
                author_email = email.split("@")[0] + "@..." if email else None

        summaries.append(
            AppSummary(
                app_id=app_id,
                display_name=display_name,
                created_at=_iso_to_dt(app_record["createdAt"]),
                updated_at=updated_at,
                features=features,
                published=True,
                author_email=author_email,
            )
        )

    summaries.sort(key=lambda s: s.updated_at or s.created_at, reverse=True)
    return DiscoverAppsResponse(apps=summaries)


@app.post("/v1/generation-jobs", response_model=CreateJobResponse)
async def create_generation_job(
    req: Request,
    request: CreateJobRequest,
    background_tasks: BackgroundTasks,
    user: dict | None = Depends(get_optional_user),
) -> CreateJobResponse:
    client_ip = req.client.host if req.client else "unknown"
    if _is_rate_limited(client_ip, "generation"):
        _raise_http(
            429, "RATE_LIMITED", "Too many generation requests, please slow down"
        )

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

    if request.app_id:
        app_record = store.get_app(request.app_id)
        if not app_record:
            _raise_http(404, "APP_NOT_FOUND", "App not found")
    else:
        owner_id = user["userId"] if user else None
        app_record = store.create_app(owner_id=owner_id)
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
