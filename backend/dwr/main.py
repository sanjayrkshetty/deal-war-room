"""Deal War Room FastAPI application (`dwr/main.py`).

Phase 1: paste-gated ingest, scrub preview, clause map, reindex.
Pipeline (Phases 3) and search (Phase 2) mount later under /api/v1.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dwr import __version__
from dwr.config import get_settings
from dwr.db import connect, init_schema
from dwr.embedder import embedder_ready, try_init_embedder
from dwr.ingest import (
    DocumentNotFound,
    DuplicateDocument,
    ingest_document,
    reindex_document,
)
from dwr.models import (
    AnalyzeCreate,
    BackfillRequest,
    DocumentCreate,
    ScrubPreviewRequest,
    SearchRequest,
)
from dwr.pipeline import PipelineError, launch_background, start_analysis
from dwr.scrubber import scrub_with_audit
from dwr.search import backfill_embeddings, search as search_clauses


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = connect()
    try:
        init_schema(conn)
        conn.execute(
            """
            UPDATE analyses SET status='failed', error='interrupted by restart',
                   finished_at=CURRENT_TIMESTAMP
            WHERE status IN ('queued','running')
            """
        )
        conn.commit()
    finally:
        conn.close()
    try_init_embedder()
    yield


def _cors_origins() -> list[str]:
    raw = os.environ.get("DWR_CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="Deal War Room API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def db_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


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
        "embedder_loaded": embedder_ready(),
    }


@app.post("/api/v1/scrub-preview")
def scrub_preview(payload: ScrubPreviewRequest) -> dict:
    result = scrub_with_audit(payload.text)
    excerpt = result["scrubbed_text"][:2000]
    return {"redactions_count": result["redactions_count"], "report": result["report"], "scrubbed_excerpt": excerpt}


@app.post("/api/v1/documents", status_code=201)
def create_document(payload: DocumentCreate, conn=Depends(db_conn)) -> dict:
    try:
        return ingest_document(
            conn,
            title=payload.title,
            source_type=payload.source_type.value,
            agency=payload.agency,
            external_ref=payload.external_ref,
            text=payload.text,
        )
    except DuplicateDocument as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/documents")
def list_documents(
    conn=Depends(db_conn),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    rows = conn.execute(
        """
        SELECT d.id, d.title, d.source_type, d.agency, d.external_ref, d.created_at,
               COUNT(c.id) AS clause_count
        FROM documents d LEFT JOIN clauses c ON c.doc_id = d.id
        GROUP BY d.id ORDER BY d.id DESC LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    return {"items": [dict(row) for row in rows], "total": total}


@app.get("/api/v1/documents/{document_id}")
def get_document(document_id: int, conn=Depends(db_conn)) -> dict:
    row = conn.execute(
        """
        SELECT id, title, source_type, agency, external_ref, created_at,
               ingest_pipeline_version, segmenter_version, scrub_report_json
        FROM documents WHERE id = ?
        """,
        (document_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    doc = dict(row)
    doc["scrub_report"] = json.loads(doc.pop("scrub_report_json"))
    doc["clause_count"] = conn.execute(
        "SELECT COUNT(*) AS n FROM clauses WHERE doc_id = ?", (document_id,)
    ).fetchone()["n"]
    return doc


@app.get("/api/v1/documents/{document_id}/clauses")
def list_clauses(document_id: int, conn=Depends(db_conn)) -> dict:
    exists = conn.execute("SELECT 1 FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="document not found")
    rows = conn.execute(
        """
        SELECT id, clause_ref, heading, body, ordinal, segmentation_mode
        FROM clauses WHERE doc_id = ? ORDER BY ordinal
        """,
        (document_id,),
    ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/v1/documents/{document_id}/reindex")
def reindex(document_id: int, conn=Depends(db_conn)) -> dict:
    try:
        return reindex_document(conn, document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@app.post("/api/v1/search")
def search_endpoint(payload: SearchRequest, conn=Depends(db_conn)) -> dict:
    from dwr.embedder import EmbedderUnavailable

    try:
        results = search_clauses(conn, payload.query, doc_id=payload.doc_id, top_k=payload.top_k)
    except EmbedderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"query": payload.query, "results": results}


@app.post("/api/v1/admin/backfill")
def admin_backfill(payload: BackfillRequest) -> dict:
    from dwr.embedder import EmbedderUnavailable

    if not embedder_ready():
        raise HTTPException(status_code=503, detail="embedder not initialized")
    conn = connect()
    try:
        init_schema(conn)
        return backfill_embeddings(conn, document_id=payload.document_id)
    except EmbedderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        conn.close()


@app.post("/api/v1/analyses", status_code=202)
def create_analysis(payload: AnalyzeCreate, conn=Depends(db_conn)) -> dict:
    exists = conn.execute(
        "SELECT 1 FROM documents WHERE id = ?", (payload.document_id,)
    ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="document not found")
    try:
        analysis_id = start_analysis(conn, payload.document_id)
    except PipelineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    launch_background(payload.document_id, analysis_id)
    return {"analysis_id": analysis_id, "status": "queued"}


@app.get("/api/v1/analyses/{analysis_id}")
def get_analysis(analysis_id: int, conn=Depends(db_conn)) -> dict:
    row = conn.execute(
        "SELECT id, doc_id, status, stage, error, started_at, finished_at FROM analyses WHERE id = ?",
        (analysis_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="analysis not found")
    return dict(row)


@app.get("/api/v1/clauses/{clause_id}")
def get_clause(clause_id: int, conn=Depends(db_conn)) -> dict:
    row = conn.execute(
        """
        SELECT c.id, c.doc_id, c.clause_ref, c.heading, c.body, c.ordinal,
               d.title AS document_title
        FROM clauses c JOIN documents d ON d.id = c.doc_id
        WHERE c.id = ?
        """,
        (clause_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="clause not found")
    return dict(row)


@app.get("/api/v1/analyses/{analysis_id}/brief")
def get_brief(analysis_id: int, conn=Depends(db_conn)) -> dict:
    import json as _json

    row = conn.execute(
        """
        SELECT b.*, a.status AS analysis_status, a.error AS analysis_error
        FROM briefs b JOIN analyses a ON a.id = b.analysis_id
        WHERE b.analysis_id = ?
        """,
        (analysis_id,),
    ).fetchone()
    if not row:
        analysis = conn.execute(
            "SELECT status, error FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        if not analysis:
            raise HTTPException(status_code=404, detail="analysis not found")
        return {"status": analysis["status"], "error": analysis["error"], "brief": None}
    brief = dict(row)
    brief["payload"] = _json.loads(brief.pop("payload_json"))
    brief["citations"] = [
        dict(c)
        for c in conn.execute(
            """
            SELECT claim_path, clause_id, quoted_span, span_start, span_end
            FROM citations WHERE brief_id = ?
            """,
            (row["id"],),
        ).fetchall()
    ]
    return {"status": "done", "error": None, "brief": brief}


@app.get("/api/v1/briefs")
def list_briefs(conn=Depends(db_conn), doc_id: int | None = Query(default=None)) -> dict:
    sql = """
        SELECT b.id, b.analysis_id, a.doc_id, b.bid_fit_score, b.recommendation,
               b.confidence, b.uncited_claims_count, b.dropped_clauses_count, b.created_at
        FROM briefs b JOIN analyses a ON a.id = b.analysis_id
    """
    params: tuple = ()
    if doc_id is not None:
        sql += " WHERE a.doc_id = ?"
        params = (doc_id,)
    rows = conn.execute(sql + " ORDER BY b.id DESC", params).fetchall()
    return {"items": [dict(row) for row in rows]}
