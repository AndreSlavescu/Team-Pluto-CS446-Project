# Pluto FastAPI Backend (MVP)

This backend implements the MVP API contract for generation jobs (uploads → async job → artifact download). It uses the OpenAI `gpt-5.2-codex` model to generate a compact blueprint and bundles it into a downloadable ZIP artifact.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your OpenAI key
uvicorn app.main:app --reload --port 8000
```

## Environment variables

- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default: `gpt-5.2-codex`)
- `PUBLIC_BASE_URL` (default: `http://localhost:8000`)
- `MAX_IMAGES` (default: `3`)
- `MAX_IMAGE_BYTES` (default: `10485760`)
- `MAX_PROMPT_CHARS` (default: `280`)

## API summary (MVP)

- `POST /v1/uploads` (multipart) → `uploadId`
- `POST /v1/generation-jobs` → `jobId`, `appId`
- `GET /v1/generation-jobs/{jobId}` → status + progress
- `GET /v1/apps/{appId}/versions/latest` → artifact metadata + download URL
- `GET /v1/apps/{appId}/versions` → version history
- `POST /v1/generation-jobs/{jobId}/cancel` → cancel job
- `GET /v1/artifacts/{artifactId}/download` → ZIP download

## Notes

- The generated ZIP contains a `blueprint.json` with a short app specification derived from the prompt + images.
- A simple `index.html`, `styles.css`, and `app.js` are included for WebView preview.
- This backend stores all data on disk under `backend/data/` (uploads, artifacts, and job state).
- The artifact `downloadUrl` is a simple backend route, not a signed external URL (can be swapped later).
