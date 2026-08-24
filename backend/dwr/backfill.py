"""Backfill CLI (`python -m dwr.backfill [--doc-id N]`)."""

from __future__ import annotations

import argparse

from dwr.db import connect, init_schema
from dwr.embedder import try_init_embedder
from dwr.search import backfill_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill clause embeddings")
    parser.add_argument("--doc-id", type=int, default=None)
    args = parser.parse_args()

    if not try_init_embedder():
        raise SystemExit("embedder unavailable — check torch install / HF cache")

    conn = connect()
    try:
        init_schema(conn)
        result = backfill_embeddings(conn, document_id=args.doc_id)
        print(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
