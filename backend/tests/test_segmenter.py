"""
Segmenter tests — heading mode, fallback mode, table preservation, fixture F1.
"""

from __future__ import annotations

import json
from pathlib import Path

from dwr.segmenter import segment

CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus" / "synthetic_samples"

NUMBERED_DOC = """1. Introduction
This tender seeks a security assessment partner.

2. Scope of Work
The vendor shall assess all systems.

2.1 Web Applications
All public-facing web applications are in scope.

3. Timeline
Work must complete within 60 days.
"""

SECTION_DOC = """Section 1: Background
Buyer is a fictional logistics enterprise.

Section 14A: DFIR Retainer SLAs
Response tiers apply per priority matrix.

Clause 4.2: Reporting
Weekly status reports are mandatory.
"""

FALLBACK_DOC = """This document has no numbered structure at all.
It just rambles across paragraphs without headings.

Here is a second paragraph continuing the rambling prose.
No section markers anywhere to be found.

A third paragraph closes the document out with more unstructured text
that should be packed into non-overlapping chunks deterministically.
"""

TABLE_DOC = """1. Deliverables
The vendor provides:

| Item | Quantity |
| Reports | 4 |

2. Payment
Net 30 days.
"""


def _refs(clauses):
    return [c.clause_ref for c in clauses]


def test_heading_mode_numbered_doc():
    clauses = segment(NUMBERED_DOC)
    assert [c.segmentation_mode for c in clauses] == ["heading"] * 4
    assert _refs(clauses) == ["1", "2", "2.1", "3"]


def test_heading_mode_section_style():
    refs = _refs(segment(SECTION_DOC))
    assert refs == ["1", "14A", "4.2"]


def test_fallback_mode_non_overlapping_full_coverage():
    clauses = segment(FALLBACK_DOC)
    assert clauses
    assert all(c.segmentation_mode == "fallback" for c in clauses)
    joined = "\n".join(c.body for c in clauses)
    for token in ["rambles", "second paragraph", "third paragraph"]:
        assert token in joined
    total = sum(len(c.body) for c in clauses)
    assert total <= len(FALLBACK_DOC)


def test_table_stays_inside_clause_body():
    clauses = segment(TABLE_DOC)
    deliverables = next(c for c in clauses if c.clause_ref == "1")
    assert "| Reports | 4 |" in deliverables.body


def _boundary_f1(expected: list[str], actual: list[str]) -> float:
    expected_set, actual_set = set(expected), set(actual)
    if not expected_set and not actual_set:
        return 1.0
    overlap = len(expected_set & actual_set)
    if overlap == 0:
        return 0.0
    precision = overlap / len(actual_set)
    recall = overlap / len(expected_set)
    return 2 * precision * recall / (precision + recall)


def _render_fixture_text(sections: list[dict]) -> str:
    blocks = []
    for section in sections:
        heading = section.get("heading") or ""
        prefix = f"{section['ref']} {heading}".rstrip()
        blocks.append(f"{prefix}\n{section['body']}")
    return "\n\n".join(blocks) + "\n"


def test_fixtures_boundary_f1_at_least_095():
    fixtures = sorted(CORPUS_DIR.glob("*.json"))
    assert fixtures, "fixture corpus missing"
    checked = 0
    for path in fixtures:
        data = json.loads(path.read_text(encoding="utf-8"))
        expected_mode = data.get("expected_mode")
        if expected_mode != "heading":
            continue
        text = _render_fixture_text(data["sections"])
        refs = _refs(segment(text))
        score = _boundary_f1(data["expected_refs"], refs)
        assert score >= 0.95, f"{path.name}: F1={score:.2f} expected={data['expected_refs']} got={refs}"
        checked += 1
    assert checked >= 3
