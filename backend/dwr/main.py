"""Deal War Room FastAPI application (`dwr/main.py`).

Phase 0 scope: schema init + health contract. Ingest/pipeline land in Phases 1-3.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from dwr import __version__
from dwr.config import get_settings
from dwr.db import connect, init_schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = connect()
    try:
        init_schema(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Deal War Room API", version=__version__, lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    try:
        conn = connect()
        try:
            db_ok = conn.execute("SELECT 1").fetchone() is not None
        finally:
            conn.close()
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db_ok": db_ok,
        "groq_key_present": bool(settings.groq_api_key),
        "embedder_loaded": False,
    }
