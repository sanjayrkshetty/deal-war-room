"""Health endpoint contract test."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dwr.config import get_settings
from dwr.main import app


def test_health_reports_db_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("DWR_DB_PATH", str(tmp_path / "health.db"))
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["db_ok"] is True
        assert isinstance(body["embedder_loaded"], bool)
        assert body["demo"]["daily_budget"] > 0
    finally:
        get_settings.cache_clear()
