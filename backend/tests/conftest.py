"""Shared test fixtures: temp DB + corpus fixture ingestion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dwr.config import get_settings
from dwr.db import connect, init_schema
from dwr.ingest import ingest_document

CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus" / "synthetic_samples"


def load_fixture(name: str) -> dict:
    return json.loads((CORPUS_DIR / name).read_text(encoding="utf-8"))


def render_fixture_text(data: dict) -> str:
    blocks = []
    for section in data["sections"]:
        heading = section.get("heading") or ""
        prefix = f"{section['ref']} {heading}".rstrip()
        blocks.append(f"{prefix}\n{section['body']}")
    return "\n\n".join(blocks) + "\n"


def ingest_fixture(conn, name: str) -> dict:
    data = load_fixture(name)
    return ingest_document(
        conn,
        title=data["title"],
        source_type=data.get("source_type", "synthetic"),
        agency=data.get("agency"),
        external_ref=None,
        text=render_fixture_text(data),
    )


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DWR_DB_PATH", str(tmp_path / "dwr.db"))
    get_settings.cache_clear()
    conn = connect()
    init_schema(conn)
    yield conn
    conn.close()
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def embedder():
    from dwr.embedder import try_init_embedder

    if not try_init_embedder():
        pytest.skip("MiniLM unavailable (first run downloads ~90MB; check torch/HF cache)")
    return True
