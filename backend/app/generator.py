from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import ZipFile

from openai import OpenAI, OpenAIError

from . import config
from .store import DataStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert Android app generator. Produce a concise JSON blueprint for a new app based on the user's one-sentence prompt and optional images.
Return ONLY valid JSON (no markdown) with this schema:
{
  "display_name": string,
  "package_name": string,
  "features": [string],
  "ui": string,
  "screens": [string],
  "data_models": [string],
  "notes": string
}
Keep values short and practical.
The app runs in a WebView with camera access available via getUserMedia. If the user's prompt involves camera, photos, scanning, QR codes, barcode reading, or AR, include the relevant camera feature in the features list.
""".strip()

EDIT_BLUEPRINT_SYSTEM_PROMPT = """
You are an expert Android app generator. You are given the HTML source of an existing app and the user's change request.
Produce an UPDATED JSON blueprint that reflects the requested changes while preserving everything else.
Return ONLY valid JSON (no markdown) with this schema:
{
  "display_name": string,
  "package_name": string,
  "features": [string],
  "ui": string,
  "screens": [string],
  "data_models": [string],
  "notes": string
}
Keep values short and practical.
""".strip()

APPDB_JS_HELPER = """
A backend data API is available for persistent, cross-device data storage. Embed this helper in a <script> block:

const AppDB = {
  _base: '{{BACKEND_URL}}/v1/apps/{{APP_ID}}/db',
  _token: localStorage.getItem('pluto_token'),
  _headers() {
    const h = {'Content-Type': 'application/json'};
    if (this._token) h['Authorization'] = 'Bearer ' + this._token;
    return h;
  },
  async list(collection, params) {
    const qs = params ? new URLSearchParams(params).toString() : '';
    const r = await fetch(this._base + '/' + collection + (qs ? '?' + qs : ''), {headers: this._headers()});
    if (!r.ok) throw new Error('AppDB list failed: ' + r.status);
    return (await r.json()).items;
  },
  async get(collection, id) {
    const r = await fetch(this._base + '/' + collection + '/' + id, {headers: this._headers()});
    if (!r.ok) throw new Error('AppDB get failed: ' + r.status);
    return r.json();
  },
  async create(collection, data) {
    const r = await fetch(this._base + '/' + collection, {
      method: 'POST', headers: this._headers(), body: JSON.stringify({data})
    });
    if (!r.ok) throw new Error('AppDB create failed: ' + r.status);
    return r.json();
  },
  async update(collection, id, data) {
    const r = await fetch(this._base + '/' + collection + '/' + id, {
      method: 'PUT', headers: this._headers(), body: JSON.stringify({data})
    });
    if (!r.ok) throw new Error('AppDB update failed: ' + r.status);
    return r.json();
  },
  async delete(collection, id) {
    const r = await fetch(this._base + '/' + collection + '/' + id, {
      method: 'DELETE', headers: this._headers()
    });
    if (!r.ok) throw new Error('AppDB delete failed: ' + r.status);
    return r.json();
  }
};

Use AppDB for data that should persist across devices or be shared between users (e.g. todo items, posts, scores).
Use localStorage only for client-only preferences (e.g. theme, last viewed tab).
Collections are created automatically on first write. Collection names must be lowercase a-z, digits, underscores (e.g. "todos", "user_scores").
The {{BACKEND_URL}} and {{APP_ID}} placeholders will be replaced automatically — use them exactly as shown.
""".strip()

CAMERA_CAPABILITY = """
Camera access is available via the standard browser getUserMedia API. The host Android app
handles runtime permission prompts automatically — generated code just needs to call the API.

When the user asks for camera features (QR scanner, photo capture, video, AR, barcode reader, etc.),
use navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }) for the rear camera
or { facingMode: 'user' } for the front/selfie camera.

Example — show a live camera preview:
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
  const video = document.createElement('video');
  video.srcObject = stream;
  video.setAttribute('playsinline', '');
  video.play();

To capture a still frame from the video feed:
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL('image/jpeg');

To stop the camera when done:
  stream.getTracks().forEach(t => t.stop());

Always wrap getUserMedia in a try/catch and show a friendly message if the user denies permission.
""".strip()

EDIT_HTML_SYSTEM_PROMPT = (
    """
You are an expert mobile web developer. You are given the HTML source of an existing app, an updated blueprint, and the user's change request.
Modify the existing HTML to implement the requested changes while preserving all untouched functionality.

Requirements:
- Single HTML file with all CSS and JavaScript inlined — no external files, no CDN links
- Mobile-first responsive layout optimised for 360-480 px width
- Every feature in the blueprint must actually work
- All buttons and forms must do something — no placeholders, no "coming soon"
- Clean modern dark UI: background #0e0f12, cards #1a1d24, accent #3bd6c6, text #f4f7ff
- Preserve existing functionality that is NOT affected by the change request
- No lorem ipsum, no sample data that isn't meaningful

"""
    + APPDB_JS_HELPER
    + "\n\n"
    + CAMERA_CAPABILITY
    + """

Return ONLY the raw HTML starting with <!doctype html>. No markdown fences, no explanation.
"""
).strip()

APP_GEN_SYSTEM_PROMPT = (
    """
You are an expert mobile web developer. Generate a complete, self-contained single-file HTML app from the blueprint and original prompt below.

Requirements:
- Single HTML file with all CSS and JavaScript inlined — no external files, no CDN links
- Mobile-first responsive layout optimised for 360-480 px width
- Every feature in the blueprint must actually work
- All buttons and forms must do something — no placeholders, no "coming soon"
- Clean modern dark UI: background #0e0f12, cards #1a1d24, accent #3bd6c6, text #f4f7ff
- No lorem ipsum, no sample data that isn't meaningful

"""
    + APPDB_JS_HELPER
    + "\n\n"
    + CAMERA_CAPABILITY
    + """

Return ONLY the raw HTML starting with <!doctype html>. No markdown fences, no explanation.
"""
).strip()


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


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None
    return None


def _inject_app_backend_url(html: str, app_id: str) -> str:
    """Replace backend URL and app ID placeholders in generated HTML."""
    base_url = config.PUBLIC_BASE_URL.rstrip("/")
    html = html.replace("{{BACKEND_URL}}", base_url)
    html = html.replace("{{APP_ID}}", app_id)
    return html


def _generate_html_app(
    blueprint: Dict[str, Any],
    prompt: str,
    client: OpenAI,
    app_id: str = "",
) -> Optional[str]:
    blueprint_text = json.dumps(blueprint, indent=2)
    try:
        response = client.responses.create(
            model=config.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": APP_GEN_SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Original prompt: {prompt}\n\nBlueprint:\n{blueprint_text}",
                        }
                    ],
                },
            ],
            max_output_tokens=65536,
        )
        html = response.output_text
        if html and app_id:
            html = _inject_app_backend_url(html, app_id)
        return html
    except Exception:
        logger.exception("HTML app generation failed")
        return None


def _validate_html(html: str) -> bool:
    """Check that generated HTML looks structurally valid."""
    stripped = html.strip().lower()
    if not stripped:
        return False
    if not (stripped.startswith("<!doctype html") or stripped.startswith("<html")):
        return False
    if "</html>" not in stripped:
        return False
    return True


def _generate_edit_blueprint(
    existing_html: str,
    change_request: str,
    client: OpenAI,
) -> Optional[Dict[str, Any]]:
    try:
        response = client.responses.create(
            model=config.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": EDIT_BLUEPRINT_SYSTEM_PROMPT}
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Change request: {change_request}\n\n"
                                f"Existing HTML:\n{existing_html}"
                            ),
                        }
                    ],
                },
            ],
            max_output_tokens=1200,
        )
        return _parse_json(response.output_text or "")
    except Exception:
        return None


def _generate_edited_html_app(
    blueprint: Dict[str, Any],
    change_request: str,
    existing_html: str,
    client: OpenAI,
    app_id: str = "",
) -> Optional[str]:
    blueprint_text = json.dumps(blueprint, indent=2)
    try:
        response = client.responses.create(
            model=config.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": EDIT_HTML_SYSTEM_PROMPT}
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Change request: {change_request}\n\n"
                                f"Updated blueprint:\n{blueprint_text}\n\n"
                                f"Existing HTML:\n{existing_html}"
                            ),
                        }
                    ],
                },
            ],
            max_output_tokens=65536,
        )
        html = response.output_text
        if html and app_id:
            html = _inject_app_backend_url(html, app_id)
        return html
    except Exception:
        return None


def _build_manifest(prompt: str, blueprint: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    display_name = None
    package_name = None
    features: List[str] = []
    ui = None
    if blueprint:
        display_name = blueprint.get("display_name")
        package_name = blueprint.get("package_name")
        ui = blueprint.get("ui")
        features = blueprint.get("features") or []

    if not display_name:
        display_name = "Pluto Generated App"
    if not package_name:
        slug = _slugify(display_name)
        package_name = f"com.pluto.generated.{slug}"

    return {
        "displayName": display_name,
        "packageName": package_name,
        "features": features,
        "ui": ui,
    }


def _create_project_bundle(
    target_dir: Path,
    prompt: str,
    blueprint: Optional[Dict[str, Any]],
    html_content: Optional[str] = None,
) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "README.md").write_text(
        "# Pluto Generated Android Project\n\n"
        "This is a generated project bundle for the Pluto MVP.\n"
        "Use the blueprint.json file as the source of truth for implementation.\n"
        "A simple HTML/CSS/JS prototype is included for WebView preview.\n"
    )
    (target_dir / "prompt.txt").write_text(prompt)
    if blueprint:
        (target_dir / "blueprint.json").write_text(json.dumps(blueprint, indent=2))
        if html_content:
            (target_dir / "index.html").write_text(html_content)
        else:
            _write_webview_bundle(target_dir, blueprint)
    else:
        (target_dir / "blueprint.txt").write_text(
            "Blueprint generation failed. See logs."
        )


def _write_webview_bundle(target_dir: Path, blueprint: Dict[str, Any]) -> None:
    display_name = blueprint.get("display_name") or "Pluto App"
    features = blueprint.get("features") or []
    screens = blueprint.get("screens") or []
    data_models = blueprint.get("data_models") or []
    notes = blueprint.get("notes") or ""

    (target_dir / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '  <meta charset="utf-8" />',
                f"  <title>{display_name}</title>",
                '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
                '  <link rel="stylesheet" href="styles.css" />',
                "</head>",
                "<body>",
                '  <div class="app">',
                '    <header class="header">',
                f"      <h1>{display_name}</h1>",
                '      <p class="subtitle">Offline-first prototype</p>',
                "    </header>",
                '    <section class="card">',
                "      <h2>Features</h2>",
                '      <ul id="features"></ul>',
                "    </section>",
                '    <section class="card">',
                "      <h2>Screens</h2>",
                '      <ul id="screens"></ul>',
                "    </section>",
                '    <section class="card">',
                "      <h2>Data Models</h2>",
                '      <ul id="models"></ul>',
                "    </section>",
                '    <section class="card notes">',
                "      <h2>Notes</h2>",
                '      <p id="notes"></p>',
                "    </section>",
                "  </div>",
                '  <script src="app.js"></script>',
                "</body>",
                "</html>",
            ]
        )
    )

    (target_dir / "styles.css").write_text(
        "\n".join(
            [
                ":root {",
                "  --bg: #0e0f12;",
                "  --card: #1a1d24;",
                "  --accent: #3bd6c6;",
                "  --text: #f4f7ff;",
                "  --muted: #9aa3b2;",
                "}",
                "* { box-sizing: border-box; }",
                "body {",
                "  margin: 0;",
                '  font-family: "Space Grotesk", system-ui, sans-serif;',
                "  background: radial-gradient(circle at top, #18202a, #0e0f12 60%);",
                "  color: var(--text);",
                "}",
                ".app {",
                "  max-width: 900px;",
                "  margin: 0 auto;",
                "  padding: 32px 20px 48px;",
                "}",
                ".header h1 {",
                "  margin: 0 0 6px;",
                "  font-size: 2.2rem;",
                "  letter-spacing: -0.02em;",
                "}",
                ".subtitle {",
                "  margin: 0 0 24px;",
                "  color: var(--muted);",
                "}",
                ".card {",
                "  background: var(--card);",
                "  border-radius: 16px;",
                "  padding: 18px 20px;",
                "  margin-bottom: 16px;",
                "  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);",
                "}",
                ".card h2 {",
                "  margin: 0 0 12px;",
                "  color: var(--accent);",
                "  font-size: 1.1rem;",
                "}",
                "ul {",
                "  margin: 0;",
                "  padding-left: 18px;",
                "  color: var(--text);",
                "}",
                ".notes p {",
                "  margin: 0;",
                "  color: var(--muted);",
                "}",
            ]
        )
    )

    (target_dir / "app.js").write_text(
        "\n".join(
            [
                "const data = {",
                f"  features: {json.dumps(features)},",
                f"  screens: {json.dumps(screens)},",
                f"  models: {json.dumps(data_models)},",
                f"  notes: {json.dumps(notes)},",
                "};",
                "",
                "function fillList(id, items) {",
                "  const list = document.getElementById(id);",
                "  list.innerHTML = '';",
                "  if (!items || items.length === 0) {",
                "    const li = document.createElement('li');",
                "    li.textContent = 'No items provided.';",
                "    list.appendChild(li);",
                "    return;",
                "  }",
                "  items.forEach((item) => {",
                "    const li = document.createElement('li');",
                "    li.textContent = item;",
                "    list.appendChild(li);",
                "  });",
                "}",
                "",
                "fillList('features', data.features);",
                "fillList('screens', data.screens);",
                "fillList('models', data.models);",
                "document.getElementById('notes').textContent = data.notes || 'No notes provided.';",
            ]
        )
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

    request = job.get("request", {})
    base_template = request.get("baseTemplate")
    is_edit = bool(base_template)

    store.set_progress(
        job_id,
        "PREPARING_INPUTS",
        10,
        "Reviewing existing app" if is_edit else "Preparing inputs",
    )
    store.add_log(
        job_id,
        "INFO",
        "Preparing edit inputs" if is_edit else "Preparing generation inputs",
    )

    prompt = request.get("prompt", "")
    constraints = request.get("constraints") or {}
    input_images = request.get("inputImages") or []

    max_seconds = (
        constraints.get("maxGenerationSeconds") or config.DEFAULT_MAX_GENERATION_SECONDS
    )
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
        content.append(
            {
                "type": "input_image",
                "image_url": _encode_image(image_path, upload["mimeType"]),
            }
        )

    store.set_progress(
        job_id,
        "CALLING_LLM",
        30,
        "Planning changes" if is_edit else "Planning app blueprint",
    )
    store.add_log(job_id, "INFO", "Calling OpenAI model")

    blueprint: Optional[Dict[str, Any]] = None
    raw_output: Optional[str] = None
    client: Optional[OpenAI] = None
    try:
        if not config.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        client = OpenAI(api_key=config.OPENAI_API_KEY)

        if is_edit:
            blueprint = _generate_edit_blueprint(base_template, prompt, client)
        else:
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
                max_output_tokens=1200,
            )
            raw_output = response.output_text
            blueprint = _parse_json(raw_output or "")
    except Exception as exc:  # pragma: no cover - defensive logging
        error_code = (
            "OPENAI_ERROR" if isinstance(exc, OpenAIError) else "GENERATION_ERROR"
        )
        store.update_job(
            job_id,
            {
                "status": "FAILED",
                "error": {
                    "code": error_code,
                    "message": str(exc),
                },
            },
        )
        store.add_log(job_id, "ERROR", f"Generation failed: {exc}")
        return

    if time.monotonic() - started_at > max_seconds:
        store.update_job(
            job_id,
            {
                "status": "FAILED",
                "error": {
                    "code": "TIMEOUT",
                    "message": "Generation exceeded time limit",
                },
            },
        )
        store.add_log(job_id, "ERROR", "Generation timed out")
        return

    if blueprint is None:
        if raw_output:
            work_dir = config.WORK_DIR / job_id
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "blueprint_raw.txt").write_text(raw_output)
        store.update_job(
            job_id,
            {
                "status": "FAILED",
                "error": {
                    "code": "BLUEPRINT_PARSE_ERROR",
                    "message": "Failed to generate a valid app blueprint. Please try rephrasing your prompt.",
                },
            },
        )
        store.add_log(job_id, "ERROR", "Blueprint JSON parsing failed")
        return

    html_content: Optional[str] = None
    if blueprint and client:
        store.set_progress(
            job_id,
            "GENERATING_APP",
            60,
            "Applying changes" if is_edit else "Generating app code",
        )
        store.add_log(
            job_id, "INFO", "Applying edits" if is_edit else "Generating functional app"
        )
        if is_edit:
            html_content = _generate_edited_html_app(
                blueprint, prompt, base_template, client, app_id=job["appId"]
            )
        else:
            html_content = _generate_html_app(
                blueprint, prompt, client, app_id=job["appId"]
            )
        if html_content is None:
            store.update_job(
                job_id,
                {
                    "status": "FAILED",
                    "error": {
                        "code": "APP_GENERATION_ERROR",
                        "message": "Failed to generate app code. Please try again.",
                    },
                },
            )
            store.add_log(job_id, "ERROR", "App code generation returned None")
            return
        if not _validate_html(html_content):
            store.update_job(
                job_id,
                {
                    "status": "FAILED",
                    "error": {
                        "code": "INVALID_HTML_OUTPUT",
                        "message": "Generated app failed validation. Please try again.",
                    },
                },
            )
            store.add_log(
                job_id, "ERROR", "Generated HTML failed structural validation"
            )
            return
        store.add_log(job_id, "INFO", "App code generated successfully")

    if time.monotonic() - started_at > max_seconds:
        store.update_job(
            job_id,
            {
                "status": "FAILED",
                "error": {
                    "code": "TIMEOUT",
                    "message": "Generation exceeded time limit",
                },
            },
        )
        store.add_log(job_id, "ERROR", "Generation timed out")
        return

    store.set_progress(
        job_id,
        "ASSEMBLING_ARTIFACT",
        80,
        "Packaging updated app" if is_edit else "Building project bundle",
    )
    store.add_log(job_id, "INFO", "Assembling artifact")

    try:
        work_dir = config.WORK_DIR / job_id
        if work_dir.exists():
            for path in work_dir.rglob("*"):
                if path.is_file():
                    path.unlink()
            for path in sorted(work_dir.rglob("*"), reverse=True):
                if path.is_dir():
                    path.rmdir()
        work_dir.mkdir(parents=True, exist_ok=True)

        _create_project_bundle(work_dir, prompt, blueprint, html_content)

        zip_path = config.ARTIFACTS_DIR / f"{job_id}_android_project.zip"
        _zip_directory(work_dir, zip_path)

        artifact_record = store.create_artifact(
            artifact_type="ANDROID_PROJECT_ZIP",
            path=zip_path,
        )

        manifest = _build_manifest(prompt, blueprint)
        version_record = store.create_version(
            app_id=job["appId"],
            job_id=job_id,
            manifest=manifest,
            artifacts=[artifact_record],
        )
    except Exception:
        logger.exception("Artifact assembly failed for job %s", job_id)
        store.update_job(
            job_id,
            {
                "status": "FAILED",
                "error": {
                    "code": "ARTIFACT_ERROR",
                    "message": "Failed to assemble app artifacts. Please try again.",
                },
            },
        )
        store.add_log(job_id, "ERROR", "Artifact assembly failed")
        return

    store.set_progress(
        job_id, "FINALIZING", 100, "Edit complete" if is_edit else "Generation complete"
    )
    store.update_job(
        job_id,
        {
            "status": "SUCCEEDED",
            "resultVersionId": version_record["versionId"],
        },
    )
    store.add_log(job_id, "INFO", "Generation succeeded")
