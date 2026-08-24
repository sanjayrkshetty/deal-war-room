"""
Live smoke test — hits the real Groq API. Deselected by default.
Run explicitly with:  uv run pytest -m live
"""

from __future__ import annotations

import time

import pytest

from dwr.config import get_settings
from dwr.pipeline import PipelineError, run_pipeline, start_analysis
from tests.conftest import ingest_fixture


@pytest.mark.live
def test_live_groq_pipeline_produces_cited_brief(db):
    if not get_settings().groq_api_key:
        pytest.fail(
            "GROQ_API_KEY is not set. Add it to backend/.env (see backend/.env.example), "
            "then run: uv run pytest -m live"
        )

    result = ingest_fixture(db, "globex_dfir_retainer_rfp.json")
    doc_id = result["document_id"]

    analysis_id = start_analysis(db, doc_id)
    start = time.perf_counter()
    outcome = run_pipeline(db, doc_id, analysis_id)
    elapsed = time.perf_counter() - start

    brief_row = db.execute(
        "SELECT * FROM briefs WHERE analysis_id=?", (analysis_id,)
    ).fetchone()
    assert brief_row is not None
    assert brief_row["recommendation"] in ("GO", "CONDITIONAL", "NO_GO")
    citations = db.execute(
        "SELECT COUNT(*) AS n FROM citations WHERE brief_id=?", (brief_row["id"],)
    ).fetchone()["n"]
    assert citations >= 1, "live run produced zero valid citations"
    assert elapsed < 90, f"pipeline took {elapsed:.0f}s (acceptance: <90s)"
