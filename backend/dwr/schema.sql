-- Deal War Room schema v1.1 (PLAN.md §data model)
-- Migrations tracked via PRAGMA user_version; bump + append ALTER scripts, never edit history.

PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (source_type IN ('synthetic', 'sam_paste', 'gem_paste', 'other_public')),
    external_ref TEXT,
    title TEXT NOT NULL,
    agency TEXT,
    raw_sha256 TEXT NOT NULL,
    ingest_pipeline_version TEXT NOT NULL,
    segmenter_version TEXT NOT NULL,
    scrubbed_text TEXT NOT NULL,
    scrub_report_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (raw_sha256, ingest_pipeline_version)
);

CREATE TABLE IF NOT EXISTS clauses (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    clause_ref TEXT NOT NULL,
    heading TEXT,
    body TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    segmentation_mode TEXT NOT NULL DEFAULT 'heading' CHECK (segmentation_mode IN ('heading', 'fallback')),
    UNIQUE (doc_id, clause_ref)
);

CREATE INDEX IF NOT EXISTS idx_clauses_doc_ordinal ON clauses (doc_id, ordinal);

CREATE TABLE IF NOT EXISTS embeddings (
    clause_id INTEGER PRIMARY KEY REFERENCES clauses (id) ON DELETE CASCADE,
    vector BLOB NOT NULL,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed')),
    stage TEXT,
    pipeline_version TEXT NOT NULL,
    model_config_json TEXT,
    error TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL UNIQUE REFERENCES analyses (id) ON DELETE CASCADE,
    bid_fit_score INTEGER CHECK (bid_fit_score BETWEEN 0 AND 100),
    recommendation TEXT NOT NULL CHECK (recommendation IN ('GO', 'CONDITIONAL', 'NO_GO')),
    confidence TEXT,
    payload_json TEXT NOT NULL,
    uncited_claims_count INTEGER NOT NULL DEFAULT 0,
    dropped_clauses_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS citations (
    brief_id INTEGER NOT NULL REFERENCES briefs (id) ON DELETE CASCADE,
    claim_path TEXT NOT NULL,
    clause_id INTEGER REFERENCES clauses (id),
    quoted_span TEXT,
    span_start INTEGER,
    span_end INTEGER,
    PRIMARY KEY (brief_id, claim_path, clause_id)
);

CREATE INDEX IF NOT EXISTS idx_citations_brief ON citations (brief_id);
