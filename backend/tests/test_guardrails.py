"""
Guardrail tests — budget accounting, rollover semantics, limiter windows,
and the analysis-entry gates.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dwr.guardrails import BudgetExceeded, RateLimiter, TokenBudget


def test_budget_accumulates_and_blocks():
    budget = TokenBudget(daily_budget=1000)
    assert budget.allow_minimum(500)
    budget.add(600)
    assert budget.used() == 600
    assert budget.remaining() == 400
    assert not budget.allow_minimum(500)
    assert budget.allow_minimum(400)


def test_limiter_sliding_window():
    limiter = RateLimiter(max_events=3, window_seconds=60)
    assert limiter.hit("ip1")
    assert limiter.hit("ip1")
    assert limiter.hit("ip1")
    assert not limiter.hit("ip1")
    assert limiter.hit("ip2"), "keys are independent"


def test_llm_client_raises_when_budget_empty(monkeypatch):
    from dwr.guardrails import token_budget
    from dwr.llm import GroqClient

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    token_budget().add(token_budget().remaining())
    client = GroqClient(api_key="test-key")
    with pytest.raises(BudgetExceeded):
        client.chat_json(stage="t", system="s", user="u", model="m")


def test_analysis_endpoint_gated_by_budget(db, monkeypatch):
    from dwr.config import get_settings

    monkeypatch.setenv("DWR_DB_PATH", str(get_settings().db_path))
    from tests.conftest import ingest_fixture

    doc = ingest_fixture(db, "globex_dfir_retainer_rfp.json")
    from dwr.guardrails import token_budget

    token_budget().add(token_budget().remaining())

    from dwr.main import app

    with TestClient(app) as client:
        resp = client.post("/api/v1/analyses", json={"document_id": doc["document_id"]})
        assert resp.status_code == 503
        assert "cap" in resp.json()["detail"].lower()
