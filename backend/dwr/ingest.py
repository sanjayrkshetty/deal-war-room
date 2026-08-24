"""Ingest pipeline (`dwr/ingest.py`).

Order is the guarantee: scrub → hash → dedupe-check → segment → persist.
Raw text exists only as a function argument; only its SHA-256 is stored.
"""

from __future__ import annotations

import hashlib
import sqlite3

from dwr.scrubber import SCRUBBER_VERSION, scrub_with_audit
from dwr.segmenter import SEGMENTER_VERSION, segment

INGEST_PIPELINE_VERSION = f"scrub{SCRUBBER_VERSION}+seg{SEGMENTER_VERSION}"


class DuplicateDocument(Exception):
    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(f"document already ingested (id={document_id})")


class DocumentNotFound(Exception):
    pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest_document(
    conn: sqlite3.Connection,
    *,
    title: str,
    source_type: str,
    agency: str | None,
    external_ref: str | None,
    text: str,
) -> dict:
    scrubbed = scrub_with_audit(text)
    raw_sha256 = _sha256(text)

    existing = conn.execute(
        "SELECT id FROM documents WHERE raw_sha256 = ? AND ingest_pipeline_version = ?",
        (raw_sha256, INGEST_PIPELINE_VERSION),
    ).fetchone()
    if existing:
        raise DuplicateDocument(existing["id"])

    clauses = segment(scrubbed["scrubbed_text"])

    try:
        cursor = conn.execute(
            """
            INSERT INTO documents (
                source_type, external_ref, title, agency, raw_sha256,
                ingest_pipeline_version, segmenter_version, scrubbed_text, scrub_report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_type,
                external_ref,
                title,
                agency,
                raw_sha256,
                INGEST_PIPELINE_VERSION,
                SEGMENTER_VERSION,
                scrubbed["scrubbed_text"],
                json_dumps(scrubbed["report"]),
            ),
        )
        doc_id = cursor.lastrowid
        conn.executemany(
            """
            INSERT INTO clauses (doc_id, clause_ref, heading, body, ordinal, segmentation_mode)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (doc_id, c.clause_ref, c.heading, c.body, c.ordinal, c.segmentation_mode)
                for c in clauses
            ],
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise DuplicateDocument(-1) from exc

    modes = sorted({c.segmentation_mode for c in clauses})
    return {
        "document_id": doc_id,
        "scrub_report": scrubbed["report"],
        "clause_count": len(clauses),
        "segmentation_modes": modes,
    }


def reindex_document(conn: sqlite3.Connection, document_id: int) -> dict:
    doc = conn.execute(
        "SELECT id, scrubbed_text FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    if not doc:
        raise DocumentNotFound(document_id)

    clauses = segment(doc["scrubbed_text"])
    try:
        conn.execute("DELETE FROM clauses WHERE doc_id = ?", (document_id,))
        conn.execute(
            "UPDATE documents SET segmenter_version = ? WHERE id = ?",
            (SEGMENTER_VERSION, document_id),
        )
        conn.executemany(
            """
            INSERT INTO clauses (doc_id, clause_ref, heading, body, ordinal, segmentation_mode)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (document_id, c.clause_ref, c.heading, c.body, c.ordinal, c.segmentation_mode)
                for c in clauses
            ],
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    return {"document_id": document_id, "clause_count": len(clauses)}


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj, sort_keys=True)
