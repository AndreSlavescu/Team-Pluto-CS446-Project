from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import ZipFile

from openai import OpenAI

from . import config
from .store import DataStore

SYSTEM_PROMPT = """
You are an expert frontend developer. Generate a COMPLETE, fully functional, single-file HTML application based on the user's prompt and optional images.

CRITICAL RULES:
- Return ONLY the raw HTML. No markdown fences, no explanation, no commentary.
- The ENTIRE app must be in ONE file: inline <style> and <script> tags.
- The app must be fully interactive and functional — buttons work, inputs work, state updates live.
- NO external dependencies. No CDN links. Everything self-contained.
- Use localStorage for any data persistence (todos, scores, settings, etc.).
- Design for mobile: max-width 420px, touch-friendly tap targets (min 44px).
- Use a modern dark theme: dark backgrounds (#0e0f12, #1a1d24), light text (#f4f7ff), vibrant accent (#3bd6c6).
- Use modern CSS: flexbox/grid, border-radius, subtle shadows, smooth transitions.
- Set a descriptive <title> tag matching the app name.
- Include <meta name="viewport" content="width=device-width, initial-scale=1">.

Make the app genuinely useful and polished — not a mockup or placeholder. If it's a todo app, items should be addable, completable, and deletable. If it's a game, it should be playable. If it's a calculator, buttons should work.
""".strip()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "", value).lower()
    return slug or "plutoapp"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _encode_image(path: Path, mime_type: str) -> str:
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_html(text: str) -> Optional[str]:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1:]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()
    if "<html" in stripped.lower() or "<!doctype" in stripped.lower():
        return stripped
    return None


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return "Pluto Generated App"


def _build_manifest(prompt: str, html: Optional[str]) -> Dict[str, Any]:
    display_name = _extract_title(html) if html else "Pluto Generated App"
    slug = _slugify(display_name)
    package_name = f"com.pluto.generated.{slug}"
    return {
        "displayName": display_name,
        "packageName": package_name,
        "features": [],
        "ui": None,
    }


def _create_project_bundle(target_dir: Path, prompt: str, html: Optional[str]) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "prompt.txt").write_text(prompt)
    if html:
        (target_dir / "index.html").write_text(html)
    else:
        (target_dir / "index.html").write_text(
            "<!doctype html><html><head><title>Error</title>"
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<style>body{background:#0e0f12;color:#f4f7ff;font-family:system-ui;display:flex;"
            "align-items:center;justify-content:center;height:100vh;margin:0;}"
            "</style></head><body><p>Generation failed. Please try again.</p></body></html>"
        )


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w") as zipf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zipf.write(path, path.relative_to(source_dir))


def run_generation_job(store: DataStore, job_id: str) -> None:
    job = store.get_job(job_id)
    if not job:
        return

    store.update_job(job_id, {"status": "RUNNING"})
    store.set_progress(job_id, "PREPARING_INPUTS", 10, "Preparing inputs")
    store.add_log(job_id, "INFO", "Preparing generation inputs")

    request = job.get("request", {})
    prompt = request.get("prompt", "")
    constraints = request.get("constraints") or {}
    input_images = request.get("inputImages") or []

    max_seconds = constraints.get("maxGenerationSeconds") or config.DEFAULT_MAX_GENERATION_SECONDS
    started_at = time.monotonic()

    if job.get("cancelRequested"):
        store.update_job(job_id, {"status": "CANCELLED"})
        return

    content = [{"type": "input_text", "text": prompt}]
    for upload_id in input_images:
        upload = store.get_upload(upload_id)
        if not upload:
            continue
        image_path = Path(upload["path"])
        content.append({
            "type": "input_image",
            "image_url": _encode_image(image_path, upload["mimeType"]),
        })

    store.set_progress(job_id, "CALLING_LLM", 40, "Generating app with AI")
    store.add_log(job_id, "INFO", "Calling OpenAI model")

    html_output: Optional[str] = None
    raw_output: Optional[str] = None
    try:
        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.responses.create(
            model=config.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": content,
                },
            ],
            max_output_tokens=16000,
        )
        raw_output = response.output_text
        html_output = _extract_html(raw_output or "")
    except Exception as exc:
        store.update_job(job_id, {
            "status": "FAILED",
            "error": {
                "code": "OPENAI_ERROR",
                "message": str(exc),
            },
        })
        store.add_log(job_id, "ERROR", f"OpenAI call failed: {exc}")
        return

    if time.monotonic() - started_at > max_seconds:
        store.update_job(job_id, {
            "status": "FAILED",
            "error": {
                "code": "TIMEOUT",
                "message": "Generation exceeded time limit",
            },
        })
        store.add_log(job_id, "ERROR", "Generation timed out")
        return

    if html_output is None:
        store.add_log(job_id, "WARN", "Could not extract HTML from model output, using raw response")
        if raw_output:
            html_output = raw_output

    store.set_progress(job_id, "ASSEMBLING_ARTIFACT", 80, "Building project bundle")
    store.add_log(job_id, "INFO", "Assembling artifact")

    work_dir = config.WORK_DIR / job_id
    if work_dir.exists():
        for path in work_dir.rglob("*"):
            if path.is_file():
                path.unlink()
        for path in sorted(work_dir.rglob("*"), reverse=True):
            if path.is_dir():
                path.rmdir()
    work_dir.mkdir(parents=True, exist_ok=True)

    _create_project_bundle(work_dir, prompt, html_output)

    zip_path = config.ARTIFACTS_DIR / f"{job_id}_android_project.zip"
    _zip_directory(work_dir, zip_path)

    artifact_record = store.create_artifact(
        artifact_type="ANDROID_PROJECT_ZIP",
        path=zip_path,
    )

    manifest = _build_manifest(prompt, html_output)
    version_record = store.create_version(
        app_id=job["appId"],
        job_id=job_id,
        manifest=manifest,
        artifacts=[artifact_record],
    )

    store.set_progress(job_id, "FINALIZING", 100, "Generation complete")
    store.update_job(job_id, {
        "status": "SUCCEEDED",
        "resultVersionId": version_record["versionId"],
    })
    store.add_log(job_id, "INFO", "Generation succeeded")
