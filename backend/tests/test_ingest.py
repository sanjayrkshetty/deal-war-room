"""
Ingest pipeline tests — the DLP guarantee, mechanically enforced.

The core assertion: after ingest, the raw text's sentinel terms exist NOWHERE
in the database file bytes. The scrub gate is tested as a property of the
persisted artifact, not of the function's return value.
"""

from __future__ import annotations

import pytest

from dwr.config import get_settings
from dwr.db import connect, init_schema
from dwr.ingest import DuplicateDocument, ingest_document, reindex_document

SENTINEL_CLIENT = "Nexora Dynamics"

RAW_TEXT = """1. Background
{client} invites proposals for a compromise assessment.

2. Scope
Contact the program office at procurement@nexora.example or +91 98765 43210.
Budget: INR 5,00,000 for 400 endpoints.

3. Reporting
Weekly findings reviews are mandatory.
""".format(client=SENTINEL_CLIENT)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DWR_DB_PATH", str(tmp_path / "ingest.db"))
    get_settings.cache_clear()
    conn = connect()
    init_schema(conn)
    yield conn
    conn.close()
    get_settings.cache_clear()


def _ingest(conn):
    return ingest_document(
        conn,
        title="Nexora CA Tender",
        source_type="synthetic",
        agency="Nexora procurement",
        external_ref=None,
        text=RAW_TEXT,
    )


def test_ingest_persists_zero_raw_bytes(db):
    result = _ingest(db)
    assert result["clause_count"] >= 3

    db_path = get_settings().db_path
    db_bytes = db_path.read_bytes()
    assert SENTINEL_CLIENT.encode() not in db_bytes
    assert b"procurement@nexora.example" not in db_bytes
    assert b"+91 98765 43210".replace(b" ", b"") not in db_bytes.replace(b" ", b"")
    assert b"5,00,000" not in db_bytes


def test_scrub_report_counts_real_substitutions(db):
    result = _ingest(db)
    report = result["scrub_report"]
    assert report["redactions_count"] >= 4
    assert report["categories"]["emails"] == 1
    assert report["categories"]["phone_numbers"] >= 1
    assert report["categories"]["financial_figures"] >= 1
    assert report["categories"]["client_names"] >= 1


def test_duplicate_text_conflicts_within_same_pipeline_version(db):
    _ingest(db)
    with pytest.raises(DuplicateDocument):
        _ingest(db)


def test_reindex_preserves_document_and_clause_coverage(db):
    first = _ingest(db)
    doc_id = first["document_id"]
    again = reindex_document(db, doc_id)
    assert again["document_id"] == doc_id
    assert again["clause_count"] == first["clause_count"]
    titles = db.execute("SELECT title FROM documents WHERE id = ?", (doc_id,)).fetchall()
    assert len(titles) == 1


def test_reindex_missing_document_raises(db):
    from dwr.ingest import DocumentNotFound

    with pytest.raises(DocumentNotFound):
        reindex_document(db, 9999)


def test_source_type_constraint_enforced(db):
    with pytest.raises(Exception):
        ingest_document(
            db,
            title="bad",
            source_type="real_client_doc",
            agency=None,
            external_ref=None,
            text="x" * 100,
        )
