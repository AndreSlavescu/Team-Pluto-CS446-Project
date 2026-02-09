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
    target_dir: Path, prompt: str, blueprint: Optional[Dict[str, Any]]
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
    store.set_progress(job_id, "PREPARING_INPUTS", 10, "Preparing inputs")
    store.add_log(job_id, "INFO", "Preparing generation inputs")

    request = job.get("request", {})
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

    store.set_progress(job_id, "CALLING_LLM", 40, "Calling GPT-5.2 Codex")
    store.add_log(job_id, "INFO", "Calling OpenAI model")

    blueprint: Optional[Dict[str, Any]] = None
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
            max_output_tokens=1200,
        )
        raw_output = response.output_text
        blueprint = _parse_json(raw_output or "")
    except Exception as exc:  # pragma: no cover - defensive logging
        store.update_job(
            job_id,
            {
                "status": "FAILED",
                "error": {
                    "code": "OPENAI_ERROR",
                    "message": str(exc),
                },
            },
        )
        store.add_log(job_id, "ERROR", f"OpenAI call failed: {exc}")
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

    if blueprint is None and raw_output:
        (work_dir / "blueprint_raw.txt").write_text(raw_output)

    _create_project_bundle(work_dir, prompt, blueprint)

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

    store.set_progress(job_id, "FINALIZING", 100, "Generation complete")
    store.update_job(
        job_id,
        {
            "status": "SUCCEEDED",
            "resultVersionId": version_record["versionId"],
        },
    )
    store.add_log(job_id, "INFO", "Generation succeeded")
