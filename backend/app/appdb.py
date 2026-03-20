"""Per-app sandboxed SQLite database manager.

Each generated app gets its own SQLite file at APPDB_DIR/{app_id}.db.
Only structured CRUD operations are exposed — no raw SQL access.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import config

COLLECTION_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

_SQLITE_RESERVED = frozenset(
    {
        "abort",
        "action",
        "add",
        "after",
        "all",
        "alter",
        "analyze",
        "and",
        "as",
        "asc",
        "attach",
        "autoincrement",
        "before",
        "begin",
        "between",
        "by",
        "cascade",
        "case",
        "cast",
        "check",
        "collate",
        "column",
        "commit",
        "conflict",
        "constraint",
        "create",
        "cross",
        "current",
        "database",
        "default",
        "deferrable",
        "deferred",
        "delete",
        "desc",
        "detach",
        "distinct",
        "drop",
        "each",
        "else",
        "end",
        "escape",
        "except",
        "exclusive",
        "exists",
        "explain",
        "fail",
        "filter",
        "following",
        "for",
        "foreign",
        "from",
        "full",
        "glob",
        "group",
        "having",
        "if",
        "ignore",
        "immediate",
        "in",
        "index",
        "indexed",
        "initially",
        "inner",
        "insert",
        "instead",
        "intersect",
        "into",
        "is",
        "isnull",
        "join",
        "key",
        "left",
        "like",
        "limit",
        "match",
        "natural",
        "no",
        "not",
        "nothing",
        "notnull",
        "null",
        "of",
        "offset",
        "on",
        "or",
        "order",
        "outer",
        "over",
        "partition",
        "plan",
        "pragma",
        "preceding",
        "primary",
        "query",
        "raise",
        "range",
        "recursive",
        "references",
        "regexp",
        "reindex",
        "release",
        "rename",
        "replace",
        "restrict",
        "right",
        "rollback",
        "row",
        "rows",
        "savepoint",
        "select",
        "set",
        "table",
        "temporary",
        "then",
        "to",
        "transaction",
        "trigger",
        "unbounded",
        "union",
        "unique",
        "update",
        "using",
        "vacuum",
        "values",
        "view",
        "virtual",
        "when",
        "where",
        "window",
        "with",
        "without",
    }
)


class AppDBError(Exception):
    """Base error for app database operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ResourceLimitError(AppDBError):
    """Raised when a resource limit is exceeded."""


class ValidationError(AppDBError):
    """Raised when input validation fails."""


class NotFoundError(AppDBError):
    """Raised when a requested resource is not found."""


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _validate_collection_name(name: str) -> None:
    if not COLLECTION_NAME_RE.match(name):
        raise ValidationError(
            "INVALID_COLLECTION_NAME",
            "Collection name must match ^[a-z][a-z0-9_]{0,62}$",
        )
    if name in _SQLITE_RESERVED:
        raise ValidationError(
            "RESERVED_COLLECTION_NAME",
            f"'{name}' is a reserved word and cannot be used as a collection name",
        )


def _quote_identifier(name: str) -> str:
    """Double-quote a SQL identifier, escaping any embedded double-quotes."""
    return '"' + name.replace('"', '""') + '"'


class _ConnectionPool:
    """Simple LRU pool of SQLite connections, one per app_id."""

    def __init__(self, max_size: int = 32) -> None:
        self._lock = threading.Lock()
        self._pool: OrderedDict[str, sqlite3.Connection] = OrderedDict()
        self._max_size = max_size

    def get(self, app_id: str) -> sqlite3.Connection:
        db_path = config.APPDB_DIR / f"{app_id}.db"
        with self._lock:
            if app_id in self._pool:
                self._pool.move_to_end(app_id)
                return self._pool[app_id]

            conn = sqlite3.connect(
                str(db_path),
                check_same_thread=False,
                isolation_level="DEFERRED",
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

            self._pool[app_id] = conn

            while len(self._pool) > self._max_size:
                _, evicted = self._pool.popitem(last=False)
                try:
                    evicted.close()
                except Exception:
                    pass

            return conn

    def close_all(self) -> None:
        with self._lock:
            for conn in self._pool.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool.clear()


_pool = _ConnectionPool()


def _get_conn(app_id: str) -> sqlite3.Connection:
    return _pool.get(app_id)


def _check_db_size(app_id: str) -> None:
    db_path = config.APPDB_DIR / f"{app_id}.db"
    if db_path.exists():
        size_bytes = os.path.getsize(db_path)
        max_bytes = config.APPDB_MAX_SIZE_MB * 1024 * 1024
        if size_bytes >= max_bytes:
            raise ResourceLimitError(
                "DB_SIZE_LIMIT",
                f"Database size limit reached ({config.APPDB_MAX_SIZE_MB}MB)",
            )


def _ensure_collection_table(conn: sqlite3.Connection, collection: str) -> None:
    """Create the collection table if it doesn't exist."""
    quoted = _quote_identifier(collection)
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {quoted} ("
        "  id TEXT PRIMARY KEY,"
        "  data TEXT NOT NULL,"
        "  created_at TEXT NOT NULL,"
        "  updated_at TEXT NOT NULL"
        ")"
    )


def list_collections(app_id: str) -> List[Dict[str, Any]]:
    conn = _get_conn(app_id)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    result = []
    for row in rows:
        name = row["name"]
        quoted = _quote_identifier(name)
        count = conn.execute(f"SELECT COUNT(*) as cnt FROM {quoted}").fetchone()["cnt"]
        result.append({"name": name, "itemCount": count})
    return result


def list_items(
    app_id: str,
    collection: str,
    *,
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at",
    filters: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    _validate_collection_name(collection)
    conn = _get_conn(app_id)

    quoted = _quote_identifier(collection)

    # Check if table exists
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (collection,),
    ).fetchone()
    if not exists:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    # Build WHERE clause from filters
    where_parts: List[str] = []
    params: List[Any] = []
    if filters:
        for field, value in filters.items():
            # Validate filter field names to prevent injection
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]{0,62}$", field):
                continue
            where_parts.append("json_extract(data, ?) = ?")
            params.append(f"$.{field}")
            params.append(value)

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    # Determine sort direction
    descending = sort.startswith("-")
    sort_field = sort.lstrip("-")
    if sort_field not in ("created_at", "updated_at", "id"):
        sort_field = "created_at"
    direction = "DESC" if descending else "ASC"

    # Get total count
    count_params = list(params)
    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM {quoted} {where_clause}",
        count_params,
    ).fetchone()["cnt"]

    # Get page
    query_params = list(params)
    query_params.extend([limit, offset])
    rows = conn.execute(
        f"SELECT id, data, created_at, updated_at FROM {quoted} "
        f"{where_clause} "
        f"ORDER BY {_quote_identifier(sort_field)} {direction} "
        f"LIMIT ? OFFSET ?",
        query_params,
    ).fetchall()

    items = [
        {
            "id": row["id"],
            "data": json.loads(row["data"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_item(app_id: str, collection: str, item_id: str) -> Dict[str, Any]:
    _validate_collection_name(collection)
    conn = _get_conn(app_id)
    quoted = _quote_identifier(collection)

    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (collection,),
    ).fetchone()
    if not exists:
        raise NotFoundError(
            "COLLECTION_NOT_FOUND", f"Collection '{collection}' not found"
        )

    row = conn.execute(
        f"SELECT id, data, created_at, updated_at FROM {quoted} WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        raise NotFoundError("ITEM_NOT_FOUND", f"Item '{item_id}' not found")

    return {
        "id": row["id"],
        "data": json.loads(row["data"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def create_item(
    app_id: str,
    collection: str,
    data: Any,
) -> Dict[str, Any]:
    _validate_collection_name(collection)
    _check_db_size(app_id)

    data_str = json.dumps(data)
    if len(data_str) > config.APPDB_MAX_ITEM_SIZE_BYTES:
        raise ResourceLimitError(
            "ITEM_TOO_LARGE",
            f"Item size exceeds limit ({config.APPDB_MAX_ITEM_SIZE_BYTES} bytes)",
        )

    conn = _get_conn(app_id)
    quoted = _quote_identifier(collection)

    # Check collection count limit
    tables = conn.execute(
        "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()["cnt"]

    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (collection,),
    ).fetchone()

    if not table_exists and tables >= config.APPDB_MAX_COLLECTIONS:
        raise ResourceLimitError(
            "MAX_COLLECTIONS",
            f"Maximum number of collections reached ({config.APPDB_MAX_COLLECTIONS})",
        )

    _ensure_collection_table(conn, collection)

    # Check item count limit
    count = conn.execute(f"SELECT COUNT(*) as cnt FROM {quoted}").fetchone()["cnt"]
    if count >= config.APPDB_MAX_ITEMS:
        raise ResourceLimitError(
            "MAX_ITEMS",
            f"Maximum items per collection reached ({config.APPDB_MAX_ITEMS})",
        )

    item_id = secrets.token_hex(8)
    now = _now_iso()

    conn.execute(
        f"INSERT INTO {quoted} (id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (item_id, data_str, now, now),
    )
    conn.commit()

    return {
        "id": item_id,
        "data": data,
        "createdAt": now,
        "updatedAt": now,
    }


def update_item(
    app_id: str,
    collection: str,
    item_id: str,
    data: Any,
) -> Dict[str, Any]:
    _validate_collection_name(collection)
    _check_db_size(app_id)

    data_str = json.dumps(data)
    if len(data_str) > config.APPDB_MAX_ITEM_SIZE_BYTES:
        raise ResourceLimitError(
            "ITEM_TOO_LARGE",
            f"Item size exceeds limit ({config.APPDB_MAX_ITEM_SIZE_BYTES} bytes)",
        )

    conn = _get_conn(app_id)
    quoted = _quote_identifier(collection)

    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (collection,),
    ).fetchone()
    if not exists:
        raise NotFoundError(
            "COLLECTION_NOT_FOUND", f"Collection '{collection}' not found"
        )

    row = conn.execute(
        f"SELECT created_at FROM {quoted} WHERE id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        raise NotFoundError("ITEM_NOT_FOUND", f"Item '{item_id}' not found")

    now = _now_iso()
    conn.execute(
        f"UPDATE {quoted} SET data = ?, updated_at = ? WHERE id = ?",
        (data_str, now, item_id),
    )
    conn.commit()

    return {
        "id": item_id,
        "data": data,
        "createdAt": row["created_at"],
        "updatedAt": now,
    }


def delete_item(app_id: str, collection: str, item_id: str) -> None:
    _validate_collection_name(collection)
    conn = _get_conn(app_id)
    quoted = _quote_identifier(collection)

    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (collection,),
    ).fetchone()
    if not exists:
        raise NotFoundError(
            "COLLECTION_NOT_FOUND", f"Collection '{collection}' not found"
        )

    deleted = conn.execute(
        f"DELETE FROM {quoted} WHERE id = ?",
        (item_id,),
    ).rowcount
    conn.commit()

    if not deleted:
        raise NotFoundError("ITEM_NOT_FOUND", f"Item '{item_id}' not found")


def drop_collection(app_id: str, collection: str) -> None:
    _validate_collection_name(collection)
    conn = _get_conn(app_id)

    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (collection,),
    ).fetchone()
    if not exists:
        raise NotFoundError(
            "COLLECTION_NOT_FOUND", f"Collection '{collection}' not found"
        )

    quoted = _quote_identifier(collection)
    conn.execute(f"DROP TABLE {quoted}")
    conn.commit()


def delete_database(app_id: str) -> None:
    """Remove an app's entire database file. Used for cleanup."""
    with _pool._lock:
        conn = _pool._pool.pop(app_id, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    db_path = config.APPDB_DIR / f"{app_id}.db"
    for suffix in ("", "-wal", "-shm"):
        p = db_path.parent / (db_path.name + suffix)
        if p.exists():
            p.unlink()
