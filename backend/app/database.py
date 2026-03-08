from __future__ import annotations

import secrets
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from . import config

_pool = None
_memory: Dict[str, Dict[str, Dict[str, Any]]] | None = None
_mem_lock = threading.Lock()


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def init_db() -> None:
    global _pool, _memory
    if not config.DATABASE_URL:
        _memory = {"users": {}, "refresh_tokens": {}}
        return

    import psycopg_pool

    _pool = psycopg_pool.ConnectionPool(config.DATABASE_URL, min_size=1, max_size=5)
    with _pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash
            ON refresh_tokens(token_hash)
            """)
        conn.commit()


def _row_to_user(row: tuple) -> Dict[str, Any]:
    return {
        "userId": row[0],
        "email": row[1],
        "hashedPassword": row[2],
        "createdAt": (
            row[3].isoformat().replace("+00:00", "Z")
            if isinstance(row[3], datetime)
            else row[3]
        ),
    }


def _row_to_token(row: tuple) -> Dict[str, Any]:
    return {
        "tokenId": row[0],
        "userId": row[1],
        "tokenHash": row[2],
        "expiresAt": (
            row[3].isoformat().replace("+00:00", "Z")
            if isinstance(row[3], datetime)
            else row[3]
        ),
        "createdAt": (
            row[4].isoformat().replace("+00:00", "Z")
            if isinstance(row[4], datetime)
            else row[4]
        ),
    }


# ── User CRUD ──


def create_user(*, email: str, hashed_password: str) -> Dict[str, Any]:
    user_id = _new_id("usr")

    if _memory is not None:
        record = {
            "userId": user_id,
            "email": email,
            "hashedPassword": hashed_password,
            "createdAt": _now_iso(),
        }
        with _mem_lock:
            _memory["users"][user_id] = record
        return record

    with _pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO users (id, email, hashed_password)
            VALUES (%s, %s, %s)
            RETURNING id, email, hashed_password, created_at
            """,
            (user_id, email, hashed_password),
        ).fetchone()
        conn.commit()
        return _row_to_user(row)


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    if _memory is not None:
        return _memory["users"].get(user_id)

    with _pool.connection() as conn:
        row = conn.execute(
            "SELECT id, email, hashed_password, created_at FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    if _memory is not None:
        for user in _memory["users"].values():
            if user["email"] == email:
                return user
        return None

    with _pool.connection() as conn:
        row = conn.execute(
            "SELECT id, email, hashed_password, created_at FROM users WHERE email = %s",
            (email,),
        ).fetchone()
        return _row_to_user(row) if row else None


def delete_user(user_id: str) -> None:
    if _memory is not None:
        with _mem_lock:
            _memory["users"].pop(user_id, None)
        return

    with _pool.connection() as conn:
        conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()


# ── Refresh Token CRUD ──


def create_refresh_token(
    *, user_id: str, token_hash: str, expires_at: str
) -> Dict[str, Any]:
    token_id = _new_id("rtk")

    if _memory is not None:
        record = {
            "tokenId": token_id,
            "userId": user_id,
            "tokenHash": token_hash,
            "expiresAt": expires_at,
            "createdAt": _now_iso(),
        }
        with _mem_lock:
            _memory["refresh_tokens"][token_id] = record
        return record

    with _pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id, user_id, token_hash, expires_at, created_at
            """,
            (token_id, user_id, token_hash, expires_at),
        ).fetchone()
        conn.commit()
        return _row_to_token(row)


def get_refresh_token_by_hash(token_hash: str) -> Optional[Dict[str, Any]]:
    if _memory is not None:
        for token in _memory["refresh_tokens"].values():
            if token["tokenHash"] == token_hash:
                return token
        return None

    with _pool.connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, token_hash, expires_at, created_at
            FROM refresh_tokens WHERE token_hash = %s
            """,
            (token_hash,),
        ).fetchone()
        return _row_to_token(row) if row else None


def delete_refresh_token(token_id: str) -> None:
    if _memory is not None:
        with _mem_lock:
            _memory["refresh_tokens"].pop(token_id, None)
        return

    with _pool.connection() as conn:
        conn.execute("DELETE FROM refresh_tokens WHERE id = %s", (token_id,))
        conn.commit()


def delete_refresh_tokens_for_user(user_id: str) -> None:
    if _memory is not None:
        with _mem_lock:
            to_remove = [
                tid
                for tid, t in _memory["refresh_tokens"].items()
                if t["userId"] == user_id
            ]
            for tid in to_remove:
                del _memory["refresh_tokens"][tid]
        return

    with _pool.connection() as conn:
        conn.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
        conn.commit()


def reset_memory() -> None:
    """Reset in-memory store. Used by tests."""
    global _memory
    if _memory is not None:
        _memory = {"users": {}, "refresh_tokens": {}}
