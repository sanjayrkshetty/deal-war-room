"""
Unit Tests for DLP Scrubber (`tests/test_scrubber.py`)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.scrubber import scrub_text, is_clean_text, scrub_with_audit


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
    assert "Email Addresses" in audit["categories_redacted"]
    assert "IP Addresses" in audit["categories_redacted"]
    assert "Client Names" in audit["categories_redacted"]
