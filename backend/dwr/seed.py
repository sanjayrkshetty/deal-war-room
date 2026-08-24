"""Boot-time fixture seeding (`dwr/seed.py`).

Showcase deployments run on ephemeral disks: every boot re-ingests the
synthetic corpus so the public demo always has content. Local dev keeps this
off (DWR_SEED_FIXTURES=false) to preserve your working DB.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dwr.ingest import DuplicateDocument, ingest_document

CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus" / "synthetic_samples"


def _render_text(sections: list[dict]) -> str:
    blocks = []
    for section in sections:
        heading = section.get("heading") or ""
        prefix = f"{section['ref']} {heading}".rstrip()
        blocks.append(f"{prefix}\n{section['body']}")
    return "\n\n".join(blocks) + "\n"


def seed_corpus(conn: sqlite3.Connection) -> dict:
    if not CORPUS_DIR.exists():
        return {"seeded": 0, "skipped": 0, "reason": "corpus dir missing"}
    seeded = skipped = 0
    for path in sorted(CORPUS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            ingest_document(
                conn,
                title=data["title"],
                source_type=data.get("source_type", "synthetic"),
                agency=data.get("agency"),
                external_ref=None,
                text=_render_text(data["sections"]),
            )
            seeded += 1
        except DuplicateDocument:
            skipped += 1
    return {"seeded": seeded, "skipped": skipped}
