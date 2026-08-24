"""Deterministic clause segmenter (`dwr/segmenter.py`).

Heading mode: numbered/§/Section/Clause/Annexure style headings split the doc;
tables and body lines stay inside their clause verbatim.
Fallback mode: no reliable headings → greedy non-overlapping paragraph packs
(C-001…) so a quoted span lives in exactly one clause.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SEGMENTER_VERSION = "1.0.0"

_FALLBACK_TARGET_CHARS = 800

_HEADING_PATTERNS: tuple[tuple[re.Pattern, int], ...] = (
    (
        re.compile(r"^(?:Section|Clause|Annexure|Annex|Appendix|Schedule)\s*([A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*)\s*[:.\-–—]?\s*(.*)$", re.IGNORECASE),
        1,
    ),
    (re.compile(r"^(?:§\s*)?(\d{1,2}(?:\.\d{1,2}){0,3}[A-Z]?)\.?\s+(\S.*?)$"), 2),
)


@dataclass(frozen=True)
class ClauseDraft:
    clause_ref: str
    heading: str | None
    body: str
    ordinal: int
    segmentation_mode: str


def _match_heading(line: str) -> tuple[str, str] | None:
    stripped = line.rstrip()
    if not stripped or len(stripped) > 140:
        return None
    for pattern, heading_group in _HEADING_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        ref = match.group(1).rstrip(".")
        heading = match.group(heading_group).strip()
        if not ref:
            continue
        if "." not in ref:
            looks_like_list_item = heading.endswith(".") or heading[:1].islower()
            if looks_like_list_item:
                return None
        return ref, heading or ""
    return None


def _segment_by_headings(text: str) -> list[ClauseDraft]:
    clauses: list[ClauseDraft] = []
    current_ref: str | None = None
    current_heading = ""
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_ref
        if current_ref is None:
            return
        body = "\n".join(buffer).strip("\n")
        clauses.append(
            ClauseDraft(
                clause_ref=current_ref,
                heading=current_heading or None,
                body=body,
                ordinal=len(clauses) + 1,
                segmentation_mode="heading",
            )
        )

    for line in text.splitlines():
        hit = _match_heading(line)
        if hit:
            flush()
            current_ref, current_heading = hit
            buffer = []
        else:
            buffer.append(line)
    flush()
    return [c for c in clauses if c.body.strip()]


def _segment_fallback(text: str) -> list[ClauseDraft]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[list[str]] = []
    size = 0
    for paragraph in paragraphs:
        if chunks and size + len(paragraph) > _FALLBACK_TARGET_CHARS:
            size = 0
            chunks.append([])
        if not chunks:
            chunks.append([])
        chunks[-1].append(paragraph)
        size += len(paragraph)
    return [
        ClauseDraft(
            clause_ref=f"C-{index:03d}",
            heading=None,
            body="\n\n".join(chunk),
            ordinal=index,
            segmentation_mode="fallback",
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def segment(text: str) -> list[ClauseDraft]:
    if not text or not text.strip():
        return []
    headed = _segment_by_headings(text)
    covered = sum(len(c.body) for c in headed)
    confident_heading_structure = len(headed) >= 3 or (
        len(headed) == 2 and covered >= 0.5 * len(text)
    )
    if confident_heading_structure:
        return headed
    fallback = _segment_fallback(text)
    return fallback if fallback else headed
