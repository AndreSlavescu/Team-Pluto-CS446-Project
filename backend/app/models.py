from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class ApiError(CamelModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class UploadResponse(CamelModel):
    upload_id: str
    mime_type: str
    size_bytes: int


class JobConstraints(CamelModel):
    platform: Optional[str] = None
    ui: Optional[str] = None
    offline_first: Optional[bool] = None
    max_generation_seconds: Optional[int] = None


class ClientInfo(CamelModel):
    device_id: Optional[str] = None
    app_version: Optional[str] = None


class CreateJobRequest(CamelModel):
    prompt: str = Field(..., min_length=1)
    input_images: List[str] = Field(default_factory=list)
    base_template: Optional[str] = None
    constraints: Optional[JobConstraints] = None
    client: Optional[ClientInfo] = None


class CreateJobResponse(CamelModel):
    job_id: str
    app_id: str
    status: str
    created_at: datetime


class JobProgress(CamelModel):
    stage: str
    percent: int
    message: Optional[str] = None


class JobLog(CamelModel):
    ts: datetime
    level: str
    msg: str


class JobStatusResponse(CamelModel):
    job_id: str
    app_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    progress: Optional[JobProgress] = None
    logs: List[JobLog] = Field(default_factory=list)
    error: Optional[ApiError] = None


class Artifact(CamelModel):
    type: str
    download_url: str
    expires_at: Optional[datetime] = None
    sha256: str


class AppManifest(CamelModel):
    display_name: str
    package_name: str
    features: List[str] = Field(default_factory=list)
    ui: Optional[str] = None


class AppVersionResponse(CamelModel):
    version_id: str
    job_id: str
    created_at: datetime
    artifacts: List[Artifact]
    manifest: AppManifest


class AppVersionsResponse(CamelModel):
    app_id: str
    versions: List[AppVersionResponse]


class CancelJobResponse(CamelModel):
    job_id: str
    status: str
    updated_at: datetime
