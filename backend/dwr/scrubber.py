"""
Local DLP Scrubber Gate (`dwr/scrubber.py`) — verbatim v1 port.

Phase 1 will fix three verified defects (see PLAN.md):
  1. _PHONE_PATTERN only matches NANP 3-3-4 grouping; Indian 10-digit/5-5 pass through.
  2. _COMMERCIAL_PATTERN misses lakh/crore grouping (₹5,00,000 half-redacts).
  3. scrub_with_audit counts categories, not actual substitutions.
"""

from __future__ import annotations

import re
from typing import TypedDict


class ScrubResult(TypedDict):
    scrubbed_text: str
    redactions_count: int
    categories_redacted: list[str]


# Patterns for DLP Sanitization
_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
_PHONE_PATTERN = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
_IP_PATTERN = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
_CREDENTIAL_PATTERN = re.compile(
    r'(?i)\b(api[_-]?key|password|secret|bearer|auth[_-]?token)\s*[:=]\s*["\']?[A-Za-z0-9_\-\.\/]{8,}["\']?'
)
_COMMERCIAL_PATTERN = re.compile(r'(?i)\b(\$|USD|INR|EUR|GBP|₹)\s*\d+(?:,\d{3})*(?:\.\d{2})?\b')

# Known organizational entity patterns to sanitize
_KNOWN_EMPLOYERS = [
    r'(?i)\bSISA\s+Information\s+Security\s+Pvt\.?\s+Ltd\.?\b',
    r'(?i)\bSISA\s+Information\s+Security\b',
    r'(?i)\bSISA\s+Technologies\b',
    r'(?i)\bSISA\b',
]

_KNOWN_CLIENTS = [
    r'(?i)\bAcme\s+Corp(?:oration)?\b',
    r'(?i)\bGlobex\s+Corporation\b',
    r'(?i)\bCyberDyne\s+Systems\b',
]


def scrub_text(text: str) -> str:
    """
    Sanitizes raw text by redacting all sensitive entities, client identifiers,
    employer references, credentials, contact information, and pricing lines.
    """
    if not text:
        return ""

    sanitized = text

    # 1. Redact Credentials & API Keys
    sanitized = _CREDENTIAL_PATTERN.sub(r'\1: [REDACTED_CREDENTIAL]', sanitized)

    # 2. Redact Emails & Phones
    sanitized = _EMAIL_PATTERN.sub('[EMAIL_ADDRESS]', sanitized)
    sanitized = _PHONE_PATTERN.sub('[PHONE_NUMBER]', sanitized)

    # 3. Redact IP Addresses
    sanitized = _IP_PATTERN.sub('[IP_ADDRESS]', sanitized)

    # 4. Redact Employer / Company Brand References
    for pattern in _KNOWN_EMPLOYERS:
        sanitized = re.sub(pattern, '[ORGANIZATION]', sanitized)

    # 5. Redact Client / Prospect Names
    for pattern in _KNOWN_CLIENTS:
        sanitized = re.sub(pattern, '[CLIENT_NAME]', sanitized)

    # 6. Redact Specific Financial Figures / Commercial Lines
    sanitized = _COMMERCIAL_PATTERN.sub('[SCRUBBED_COMMERCIAL]', sanitized)

    return sanitized


def scrub_with_audit(text: str) -> ScrubResult:
    """
    Sanitizes text and returns detailed audit metrics on what was redacted.
    """
    original = text
    scrubbed = scrub_text(text)

    categories: set[str] = set()
    if _EMAIL_PATTERN.search(original):
        categories.add("Email Addresses")
    if _PHONE_PATTERN.search(original):
        categories.add("Phone Numbers")
    if _IP_PATTERN.search(original):
        categories.add("IP Addresses")
    if _CREDENTIAL_PATTERN.search(original):
        categories.add("Credentials/API Keys")
    if _COMMERCIAL_PATTERN.search(original):
        categories.add("Financial Figures")

    for pattern in _KNOWN_EMPLOYERS:
        if re.search(pattern, original):
            categories.add("Employer Identifiers")

    for pattern in _KNOWN_CLIENTS:
        if re.search(pattern, original):
            categories.add("Client Names")

    diff_length = max(0, len(original) - len(scrubbed))
    count = len(categories)

    return {
        "scrubbed_text": scrubbed,
        "redactions_count": count,
        "categories_redacted": sorted(list(categories)),
    }


def is_clean_text(text: str) -> bool:
    """
    Checks if text is clean of unscrubbed credentials, emails, or employer references.
    """
    if not text:
        return True
    return scrub_text(text) == text
