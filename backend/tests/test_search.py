"""
Search tests — Phase 2 acceptance from PLAN.md.

Relevance: SLA question must retrieve the SLA clause top-3 on its document.
Determinism: identical inputs produce byte-identical vectors per model version.
Latency: warm search over 500 clauses < 200ms.
"""

from __future__ import annotations

import time

import numpy as np

from dwr.embedder import encode_texts
from dwr.search import backfill_embeddings, search
from tests.conftest import ingest_fixture, load_fixture


def test_deterministic_vectors(embedder):
    a = encode_texts(["Incident response SLA within 15 minutes"])
    b = encode_texts(["Incident response SLA within 15 minutes"])
    assert a[0].tobytes() == b[0].tobytes()
    assert a.shape == (1, 384)


def test_sla_question_retrieves_sla_clause_top3(db, embedder):
    result = ingest_fixture(db, "globex_dfir_retainer_rfp.json")
    backfill_embeddings(db, document_id=result["document_id"])

    hits = search(
        db,
        "What is the incident response SLA and initial response time?",
        doc_id=result["document_id"],
        top_k=3,
    )
    refs = [hit["clause_ref"] for hit in hits]
    assert "2" in refs, f"SLA clause missing from top-3: {refs}"
    assert hits[0]["score"] >= 0.3


def test_cross_document_retrieval_finds_penalty_clause(db, embedder):
    ingest_fixture(db, "acme_vapt_rfp.json")
    cyber = ingest_fixture(db, "cyberdyne_grc_rfp.json")
    backfill_embeddings(db)

    hits = search(db, "liquidated damages penalty for schedule delay", top_k=3)
    top = [(hit["doc_id"], hit["clause_ref"]) for hit in hits]
    assert (cyber["document_id"], "3") in top, f"LD clause not retrieved: {top}"


def test_warm_search_latency_under_200ms_at_500_clauses(db, embedder):
    ingest_fixture(db, "globex_dfir_retainer_rfp.json")
    base_vectors = encode_texts([f"Clause variant {i} covering scope item {i}" for i in range(500)])

    doc_row = db.execute("SELECT id FROM documents LIMIT 1").fetchone()
    doc_id = doc_row["id"]
    db.execute("DELETE FROM clauses WHERE doc_id = ?", (doc_id,))
    db.execute("DELETE FROM embeddings WHERE clause_id NOT IN (SELECT id FROM clauses)")
    rows = [
        (doc_id, f"C-{i:03d}", None, f"Synthetic clause body number {i} about security scope.", i, "fallback")
        for i in range(1, 501)
    ]
    db.executemany(
        "INSERT INTO clauses (doc_id, clause_ref, heading, body, ordinal, segmentation_mode) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    ids = [r[0] for r in db.execute("SELECT id FROM clauses WHERE doc_id = ? ORDER BY ordinal", (doc_id,)).fetchall()]
    db.executemany(
        "INSERT INTO embeddings (clause_id, vector, model, dim) VALUES (?, ?, 'test@local', 384)",
        [(cid, base_vectors[i].tobytes()) for i, cid in enumerate(ids[:500])],
    )
    db.commit()

    start = time.perf_counter()
    hits = search(db, "scope items for assessment", doc_id=doc_id, top_k=8)
    elapsed = time.perf_counter() - start

    assert len(hits) == 8
    scores = [hit["score"] for hit in hits]
    assert scores == sorted(scores, reverse=True)
    assert elapsed < 0.2, f"warm search took {elapsed*1000:.0f}ms"


def test_canary_fixture_ingests_and_segments(db, embedder):
    data = load_fixture("injection_canary.json")
    from tests.conftest import render_fixture_text
    from dwr.ingest import ingest_document

    result = ingest_document(
        db,
        title=data["title"],
        source_type="synthetic",
        agency=data["agency"],
        external_ref=None,
        text=render_fixture_text(data),
    )
    assert result["clause_count"] >= 1
