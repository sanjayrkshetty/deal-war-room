"""SQLite connection factory (`dwr/db.py`).

PRAGMAs are per-connection in SQLite: they are applied on EVERY open here.
Never bypass this factory with raw sqlite3.connect().
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from dwr.config import get_settings

_CONNECTION_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    for pragma in _CONNECTION_PRAGMAS:
        conn.execute(pragma)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def verify_schema(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
    ).fetchone()
    return row is not None
