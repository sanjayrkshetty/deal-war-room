"""
Citation enforcement unit tests — adversarial cases from critic B3 spec.
"""

from __future__ import annotations

import pytest

from dwr.enforce import enforce_claims, validate_span

GOOD_BODY = (
    "The vendor shall provide initial remote response within fifteen minutes of alert "
    "acknowledgement every day of the year, including public holidays and weekends."
)
OTHER_BODY = (
    "All deliverables are subject to acceptance testing by the client security office "
    "prior to final milestone sign-off and payment release."
)


def test_valid_span_passes_with_offsets():
    span = GOOD_BODY[:120]
    ok, start, end, err = validate_span(span, GOOD_BODY)
    assert ok
    assert start is not None and end is not None and end > start
    assert GOOD_BODY[start:end].replace("\n", " ").startswith(span.split()[0])


def test_real_span_from_wrong_clause_fails():
    span = OTHER_BODY[:120]
    ok, _, _, err = validate_span(span, GOOD_BODY)
    assert not ok


def test_short_span_rejected_even_if_verbatim():
    ok, _, _, err = validate_span("within fifteen minutes", GOOD_BODY)
    assert not ok
    assert "too short" in (err or "")


def test_generic_tiny_span_cannot_spoof_citation():
    ok, _, _, err = validate_span("the vendor shall provide", OTHER_BODY)
    assert not ok


def test_missing_clause_id_rejected():
    sections = {
        "scope_traps": [
            {"title": "Tight SLA", "severity": "HIGH", "why_trap": "sub-hour commitment",
             "evidence": [{"clause_id": 9999, "quoted_span": GOOD_BODY[:100]}]}
        ]
    }
    result = enforce_claims(sections, {1: GOOD_BODY})
    assert result.uncited_count == 1
    assert any("does not exist" in e for e in result.validation_errors)


def test_clean_item_gets_clause_ids_and_offsets():
    sections = {
        "key_dates": [
            {"label": "Initial response", "value": "15 minutes",
             "evidence": [{"clause_id": 7, "quoted_span": GOOD_BODY[:140]}]}
        ]
    }
    result = enforce_claims(sections, {7: GOOD_BODY})
    assert result.uncited_count == 0
    assert result.clean_items[0]["clause_ids"] == [7]
    assert result.citations[0]["span_start"] is not None
