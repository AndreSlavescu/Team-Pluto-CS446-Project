from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class DataStore:
    def __init__(self, state_path: Path) -> None:
        self._lock = threading.Lock()
        self._state_path = state_path
        self._state: Dict[str, Any] = {
            "uploads": {},
            "jobs": {},
            "apps": {},
            "versions": {},
            "artifacts": {},
        }
        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self) -> None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        config.WORK_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text())
        except json.JSONDecodeError:
            return
        if isinstance(data, dict):
            self._state.update(data)

    def _save(self) -> None:
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2, sort_keys=True))
        tmp.replace(self._state_path)

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(8)}"

    def create_upload(
        self, *, content: bytes, filename: str, mime_type: str
    ) -> Dict[str, Any]:
        upload_id = self._new_id("upl")
        suffix = Path(filename).suffix or ""
        path = config.UPLOADS_DIR / f"{upload_id}{suffix}"
        path.write_bytes(content)
        record = {
            "uploadId": upload_id,
            "path": str(path),
            "mimeType": mime_type,
            "sizeBytes": len(content),
            "createdAt": _iso(_now()),
        }
        with self._lock:
            self._state["uploads"][upload_id] = record
            self._save()
        return record

    def get_upload(self, upload_id: str) -> Optional[Dict[str, Any]]:
        return self._state["uploads"].get(upload_id)

    def create_app(self) -> Dict[str, Any]:
        app_id = self._new_id("app")
        record = {
            "appId": app_id,
            "createdAt": _iso(_now()),
            "versionIds": [],
            "latestVersionId": None,
        }
        with self._lock:
            self._state["apps"][app_id] = record
            self._save()
        return record

    def get_app(self, app_id: str) -> Optional[Dict[str, Any]]:
        return self._state["apps"].get(app_id)

    def create_job(self, *, app_id: str, request: Dict[str, Any]) -> Dict[str, Any]:
        job_id = self._new_id("job")
        now = _now()
        record = {
            "jobId": job_id,
            "appId": app_id,
            "status": "QUEUED",
            "createdAt": _iso(now),
            "updatedAt": _iso(now),
            "progress": None,
            "logs": [],
            "error": None,
            "request": request,
            "cancelRequested": False,
        }
        with self._lock:
            self._state["jobs"][job_id] = record
            self._save()
        return record

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._state["jobs"].get(job_id)

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        with self._lock:
            job = self._state["jobs"].get(job_id)
            if not job:
                return
            job.update(updates)
            job["updatedAt"] = _iso(_now())
            self._save()

    def add_log(self, job_id: str, level: str, msg: str) -> None:
        with self._lock:
            job = self._state["jobs"].get(job_id)
            if not job:
                return
            job["logs"].append({"ts": _iso(_now()), "level": level, "msg": msg})
            job["updatedAt"] = _iso(_now())
            self._save()

    def set_progress(
        self, job_id: str, stage: str, percent: int, message: str | None = None
    ) -> None:
        self.update_job(
            job_id,
            {
                "progress": {
                    "stage": stage,
                    "percent": percent,
                    "message": message,
                }
            },
        )

    def request_cancel(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._state["jobs"].get(job_id)
            if not job:
                return None
            job["cancelRequested"] = True
            job["updatedAt"] = _iso(_now())
            self._save()
            return job

    def create_artifact(
        self, *, artifact_type: str, path: Path, ttl_hours: int = 1
    ) -> Dict[str, Any]:
        artifact_id = self._new_id("art")
        now = _now()
        record = {
            "artifactId": artifact_id,
            "type": artifact_type,
            "path": str(path),
            "createdAt": _iso(now),
            "expiresAt": _iso(now + timedelta(hours=ttl_hours)),
        }
        with self._lock:
            self._state["artifacts"][artifact_id] = record
            self._save()
        return record

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        return self._state["artifacts"].get(artifact_id)

    def create_version(
        self,
        *,
        app_id: str,
        job_id: str,
        manifest: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        version_id = self._new_id("ver")
        record = {
            "versionId": version_id,
            "appId": app_id,
            "jobId": job_id,
            "createdAt": _iso(_now()),
            "manifest": manifest,
            "artifactIds": [a["artifactId"] for a in artifacts],
        }
        with self._lock:
            self._state["versions"][version_id] = record
            app = self._state["apps"].get(app_id)
            if app:
                app["versionIds"].append(version_id)
                app["latestVersionId"] = version_id
            self._save()
        return record

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        return self._state["versions"].get(version_id)

    def list_versions(self, app_id: str) -> List[Dict[str, Any]]:
        app = self._state["apps"].get(app_id)
        if not app:
            return []
        return [
            self._state["versions"][vid]
            for vid in app["versionIds"]
            if vid in self._state["versions"]
        ]

    @staticmethod
    def parse_iso(value: str) -> datetime:
        return _parse_iso(value)


store = DataStore(config.STATE_PATH)
