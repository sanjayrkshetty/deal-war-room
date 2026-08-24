"""DLP scrubber v2 (`dwr/scrubber.py`).

Fixes over the v1 port (see PLAN.md):
  - Indian mobile formats (+91 / 10-digit / 5-5 grouping) now redacted
  - lakh/crore commercial grouping (INR 5,00,000) fully redacted
  - audit counts actual substitutions per category, never categories-as-counts
  - entity lists are config-driven (`entities.yaml`)
Audit reports carry categories, counts and hashes only — never matched strings.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import yaml

SCRUBBER_VERSION = "2.0.0"

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

_PHONE_INTL = re.compile(r"\+\d{1,3}[\s.-]?(?:\d{2,5}[\s.-]?){1,4}\d{2,5}")
_PHONE_IND = re.compile(r"(?:\+91[\s.-]?)?\b[6-9]\d{4}[\s.-]?\d{5}\b")
_PHONE_NANP = re.compile(r"\b(?:\+?1[\s.-]?)?(?:\(\d{3}\)[\s.-]|\d{3}[\s.-])\d{3}[\s.-]\d{4}\b")
_PHONE_PATTERNS = (_PHONE_INTL, _PHONE_IND, _PHONE_NANP)

_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|password|secret|bearer|auth[_-]?token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-.\/]{8,}[\"']?"
)

_COMMERCIAL_PATTERN = re.compile(
    r"(?i)\b(?:₹|Rs\.?|INR|USD|EUR|GBP|[$€£])\s*\d[\d,]*(?:\.\d{1,2})?"
)


class ScrubResult(TypedDict):
    scrubbed_text: str
    redactions_count: int
    categories_redacted: list[str]
    report: dict


@lru_cache(maxsize=1)
def _entity_patterns() -> tuple[list[re.Pattern], list[re.Pattern]]:
    config_path = Path(__file__).parent / "entities.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    employers = [re.compile(p, re.IGNORECASE) for p in raw.get("employers", [])]
    clients = [re.compile(p, re.IGNORECASE) for p in raw.get("clients", [])]
    return employers, clients


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scrub_text(text: str) -> str:
    if not text:
        return ""
    employers, clients = _entity_patterns()
    sanitized = _CREDENTIAL_PATTERN.sub(r"\1: [REDACTED_CREDENTIAL]", text)
    sanitized = _EMAIL_PATTERN.sub("[EMAIL_ADDRESS]", sanitized)
    sanitized = _IP_PATTERN.sub("[IP_ADDRESS]", sanitized)
    for pattern in _PHONE_PATTERNS:
        sanitized = pattern.sub("[PHONE_NUMBER]", sanitized)
    for pattern in employers:
        sanitized = pattern.sub("[ORGANIZATION]", sanitized)
    for pattern in clients:
        sanitized = pattern.sub("[CLIENT_NAME]", sanitized)
    sanitized = _COMMERCIAL_PATTERN.sub("[SCRUBBED_COMMERCIAL]", sanitized)
    return sanitized


def scrub_with_audit(text: str) -> ScrubResult:
    if not text:
        return {
            "scrubbed_text": "",
            "redactions_count": 0,
            "categories_redacted": [],
            "report": {"scrubber_version": SCRUBBER_VERSION, "categories": {}, "input_sha256": "", "output_sha256": ""},
        }

    employers, clients = _entity_patterns()
    working = text
    categories: dict[str, int] = {}

    def _apply(name: str, pattern: re.Pattern, replacement: str) -> None:
        nonlocal working
        working, n = pattern.subn(replacement, working)
        if n:
            categories[name] = categories.get(name, 0) + n

    _apply("credentials", _CREDENTIAL_PATTERN, r"\1: [REDACTED_CREDENTIAL]")
    _apply("emails", _EMAIL_PATTERN, "[EMAIL_ADDRESS]")
    _apply("ip_addresses", _IP_PATTERN, "[IP_ADDRESS]")
    for pattern in _PHONE_PATTERNS:
        _apply("phone_numbers", pattern, "[PHONE_NUMBER]")
    for pattern in employers:
        _apply("employer_identifiers", pattern, "[ORGANIZATION]")
    for pattern in clients:
        _apply("client_names", pattern, "[CLIENT_NAME]")
    _apply("financial_figures", _COMMERCIAL_PATTERN, "[SCRUBBED_COMMERCIAL]")

    report = {
        "scrubber_version": SCRUBBER_VERSION,
        "redactions_count": sum(categories.values()),
        "categories": categories,
        "input_sha256": _sha256(text),
        "output_sha256": _sha256(working),
    }
    return {
        "scrubbed_text": working,
        "redactions_count": report["redactions_count"],
        "categories_redacted": sorted(categories.keys()),
        "report": report,
    }


def is_clean_text(text: str) -> bool:
    if not text:
        return True
    return scrub_text(text) == text
