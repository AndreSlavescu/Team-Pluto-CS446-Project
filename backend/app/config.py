from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", DATA_DIR / "uploads"))
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", DATA_DIR / "artifacts"))
WORK_DIR = Path(os.getenv("WORK_DIR", DATA_DIR / "work"))
STATE_PATH = Path(os.getenv("STATE_PATH", DATA_DIR / "state.json"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2-codex")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", "10485760"))
MAX_IMAGES = int(os.getenv("MAX_IMAGES", "3"))
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "280"))

DEFAULT_MAX_GENERATION_SECONDS = int(os.getenv("DEFAULT_MAX_GENERATION_SECONDS", "240"))

DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL", "")

JWT_SECRET = os.getenv("JWT_SECRET", "")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# Per-app sandboxed database settings
APPDB_DIR = Path(os.getenv("APPDB_DIR", DATA_DIR / "appdb"))
APPDB_MAX_SIZE_MB = int(os.getenv("APPDB_MAX_SIZE_MB", "50"))
APPDB_MAX_COLLECTIONS = int(os.getenv("APPDB_MAX_COLLECTIONS", "20"))
APPDB_MAX_ITEMS = int(os.getenv("APPDB_MAX_ITEMS", "10000"))
APPDB_MAX_ITEM_SIZE_BYTES = int(os.getenv("APPDB_MAX_ITEM_SIZE_BYTES", "65536"))
