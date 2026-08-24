"""Embedding backfill + brute-force cosine search (`dwr/search.py`).

Scale contract: hundreds of clauses → numpy over all rows is correct here.
Revisit trigger (PLAN.md): ~10k clauses → move to a vector index.
"""

from __future__ import annotations

import sqlite3

import numpy as np

from dwr.embedder import EmbedderUnavailable, encode_texts, loaded_model_tag


def backfill_embeddings(conn: sqlite3.Connection, document_id: int | None = None) -> dict:
    sql = """
        SELECT c.id, c.heading, c.body
        FROM clauses c LEFT JOIN embeddings e ON e.clause_id = c.id
        WHERE e.clause_id IS NULL
    """
    params: tuple = ()
    if document_id is not None:
        sql += " AND c.doc_id = ?"
        params = (document_id,)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return {"embedded": 0, "model_tag": loaded_model_tag()}

    texts = [
        f"{row['heading']}\n{row['body']}" if row["heading"] else row["body"]
        for row in rows
    ]
    vectors = encode_texts(texts)
    model_tag = loaded_model_tag()
    conn.executemany(
        "INSERT OR REPLACE INTO embeddings (clause_id, vector, model, dim) VALUES (?, ?, ?, ?)",
        [
            (row["id"], vectors[i].tobytes(), model_tag, int(vectors.shape[1]))
            for i, row in enumerate(rows)
        ],
    )
    conn.commit()
    return {"embedded": len(rows), "model_tag": model_tag}


def _snippet(body: str, limit: int = 240) -> str:
    compact = " ".join(body.split())
    return compact[:limit] + ("…" if len(compact) > limit else "")


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    doc_id: int | None = None,
    top_k: int = 8,
) -> list[dict]:
    try:
        query_vector = encode_texts([query])[0]
    except EmbedderUnavailable:
        raise
    except Exception as exc:
        raise EmbedderUnavailable(f"query encoding failed: {exc}") from exc

    sql = """
        SELECT e.clause_id, e.vector, c.doc_id, c.clause_ref, c.heading, c.body
        FROM embeddings e JOIN clauses c ON c.id = e.clause_id
    """
    params: list = []
    if doc_id is not None:
        sql += " WHERE c.doc_id = ?"
        params.append(doc_id)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return []

    matrix = np.vstack([np.frombuffer(row["vector"], dtype=np.float32) for row in rows])
    scores = matrix @ query_vector
    order = np.argsort(-scores)[:top_k]

    results = []
    for index in order:
        row = rows[int(index)]
        results.append(
            {
                "clause_id": row["clause_id"],
                "doc_id": row["doc_id"],
                "clause_ref": row["clause_ref"],
                "heading": row["heading"],
                "score": float(scores[index]),
                "snippet": _snippet(row["body"]),
            }
        )
    return results
