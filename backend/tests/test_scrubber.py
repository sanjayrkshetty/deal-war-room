"""
Unit Tests for DLP Scrubber (`tests/test_scrubber.py`)
"""

from __future__ import annotations

from dwr.scrubber import scrub_text, is_clean_text, scrub_with_audit


def test_scrub_text_redacts_credentials():
    raw = "api_key: 'sk-1234567890abcdef1234567890' and password: 'SecretPassword123'"
    scrubbed = scrub_text(raw)
    assert "[REDACTED_CREDENTIAL]" in scrubbed
    assert "sk-1234567890abcdef1234567890" not in scrubbed


def test_scrub_text_redacts_contact_info():
    raw = "Contact john.doe@sisa.com or call +1-555-123-4567 at IP 192.168.1.50"
    scrubbed = scrub_text(raw)
    assert "[EMAIL_ADDRESS]" in scrubbed
    assert "[PHONE_NUMBER]" in scrubbed
    assert "[IP_ADDRESS]" in scrubbed
    assert "john.doe@sisa.com" not in scrubbed
    assert "192.168.1.50" not in scrubbed


def test_scrub_text_redacts_employer_and_client_names():
    raw = "SISA Information Security Pvt. Ltd. delivered a proposal to Acme Corporation."
    scrubbed = scrub_text(raw)
    assert "[ORGANIZATION]" in scrubbed
    assert "[CLIENT_NAME]" in scrubbed
    assert "SISA Information Security" not in scrubbed
    assert "Acme Corporation" not in scrubbed


def test_scrub_with_audit():
    raw = "Acme Corp proposal from test@sisa.com with IP 10.0.0.1"
    audit = scrub_with_audit(raw)
    assert audit["redactions_count"] >= 3
    assert "emails" in audit["categories_redacted"]
    assert "ip_addresses" in audit["categories_redacted"]
    assert "client_names" in audit["categories_redacted"]


def test_is_clean_text_roundtrip():
    raw = "Clean scope text about a 500-endpoint compromise assessment."
    assert is_clean_text(raw) is True
    dirty = "Email me at ops@vendor.example for the quote."
    assert is_clean_text(dirty) is False


def test_indian_phone_formats_redacted():
    samples = [
        "+91 98765 43210",
        "9876543210",
        "98765-43210",
        "+91-80-41234567",
    ]
    for raw in samples:
        scrubbed = scrub_text(f"Call {raw} now.")
        assert "[PHONE_NUMBER]" in scrubbed, f"missed: {raw}"
        assert raw not in scrubbed


def test_effort_numbers_survive_scrub():
    raw = "Assessment covers 500 endpoints within 120 hours and 24x7 monitoring."
    scrubbed = scrub_text(raw)
    assert scrubbed == raw


def test_lakh_grouping_fully_redacted():
    raw = "Total outlay INR 5,00,000 plus GST."
    scrubbed = scrub_text(raw)
    assert "[SCRUBBED_COMMERCIAL]" in scrubbed
    assert "5,00,000" not in scrubbed
    assert "[SCRUBBED_COMMERCIAL]00,000" not in scrubbed


def test_audit_counts_substitutions_not_categories():
    raw = (
        "Mail a@x.com and b@y.com, ring +91 98765 43210, "
        "budget INR 1,00,000 and INR 2,50,000."
    )
    audit = scrub_with_audit(raw)
    assert audit["report"]["categories"]["emails"] == 2
    assert audit["report"]["categories"]["financial_figures"] == 2
    assert audit["redactions_count"] >= 5


def test_report_never_contains_matched_strings():
    secret = "agent@vendor-internal.example"
    audit = scrub_with_audit(f"Ping {secret} about INR 9,99,999.")
    blob = str(audit["report"])
    assert secret not in blob
    assert "9,99,999" not in blob
