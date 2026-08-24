"""Analyze CLI (`python -m dwr.analyze <doc_id>`) — synchronous pipeline runner."""

from __future__ import annotations

import argparse
import json
import sys

from dwr.db import connect, init_schema
from dwr.pipeline import PipelineError, run_pipeline, start_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Deal War Room pipeline on a document")
    parser.add_argument("doc_id", type=int)
    args = parser.parse_args()

    conn = connect()
    try:
        init_schema(conn)
        analysis_id = start_analysis(conn, args.doc_id)
        result = run_pipeline(conn, args.doc_id, analysis_id)
        brief_row = conn.execute(
            "SELECT payload_json FROM briefs WHERE id = ?", (result["brief_id"],)
        ).fetchone()
        print(json.dumps(json.loads(brief_row["payload_json"]), indent=2))
    except PipelineError as exc:
        print(f"pipeline error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
