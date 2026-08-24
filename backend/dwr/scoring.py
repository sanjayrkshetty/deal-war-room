"""Verdict engine (`dwr/scoring.py`).

The LLM proposes signals; THIS module decides. Score and recommendation are
computed deterministically from the versioned rubric — never from model
output. rubric.local.yaml (gitignored) overrides public-safe defaults.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RUBRIC_PATH = Path(__file__).parent / "rubric.yaml"
LOCAL_OVERRIDE_NAME = "rubric.local.yaml"

BASE_SCORE = 60
TRAP_DEDUCTIONS = {"HIGH": 12, "MED": 6, "LOW": 2}
GO_THRESHOLD = 70
CONDITIONAL_CEILING = 69


class RubricInconsistency(ValueError):
    pass


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=1)
def load_rubric() -> dict[str, Any]:
    rubric = yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))
    local_path = RUBRIC_PATH.parent / LOCAL_OVERRIDE_NAME
    if local_path.exists():
        override = yaml.safe_load(local_path.read_text(encoding="utf-8")) or {}
        rubric = _deep_merge(rubric, override)
    return rubric


def rubric_version() -> str:
    return str(load_rubric().get("version", "0"))


def _signal_hits(text: str, signals: list[dict]) -> list[str]:
    hits = []
    for signal in signals or []:
        pattern = signal.get("match")
        if pattern and re.search(pattern, text):
            hits.append(signal["id"])
    return hits


def compute_verdict(
    *,
    risk_output: dict,
    brief_draft: dict,
    scrubbed_text: str,
) -> dict:
    rubric = load_rubric()
    weights = rubric["score_weights"]

    traps = risk_output.get("scope_traps", [])
    drivers = risk_output.get("effort_drivers", [])
    matrix = brief_draft.get("service_line_matrix", [])

    score = BASE_SCORE

    high_traps = [t for t in traps if t.get("severity") == "HIGH"]
    med_traps = [t for t in traps if t.get("severity") == "MED"]
    low_traps = [t for t in traps if t.get("severity") == "LOW"]
    score -= TRAP_DEDUCTIONS["HIGH"] * len(high_traps)
    score -= TRAP_DEDUCTIONS["MED"] * len(med_traps)
    score -= TRAP_DEDUCTIONS["LOW"] * len(low_traps)

    fits = [entry.get("fit") for entry in matrix]
    requested = [f for f in fits if f != "NOT_REQUESTED"]
    if requested:
        coverage_ratio = requested.count("STRONG") / len(requested)
        score += int(round(weights["capability_coverage"] * (coverage_ratio - 0.5) / 2))
    weak_count = fits.count("WEAK")
    score -= min(10, 2 * weak_count)

    high_impact_drivers = sum(1 for d in drivers if "high" in str(d.get("impact", "")).lower())
    score -= min(15, 5 * high_impact_drivers)

    sla_high = any("sla" in str(t.get("why_trap", "")).lower() or "sla" in str(t.get("title", "")).lower()
                   for t in high_traps)
    if sla_high:
        score = min(score, CONDITIONAL_CEILING)

    haystack = "\n".join(
        [scrubbed_text]
        + [f"{t.get('title', '')} {t.get('why_trap', '')}" for t in traps]
    )
    no_go_hits = _signal_hits(haystack, rubric.get("no_go_signals", []))
    conditional_hits = _signal_hits(haystack, rubric.get("conditional_signals", []))

    if no_go_hits or score < 40:
        recommendation = "NO_GO"
    elif score < GO_THRESHOLD or conditional_hits:
        recommendation = "CONDITIONAL"
    else:
        recommendation = "GO"

    if recommendation == "NO_GO" and not no_go_hits and score >= 40:
        raise RubricInconsistency("recommendation/score mismatch detected by consistency check")

    deduction_notes = (
        f"{len(high_traps)} HIGH / {len(med_traps)} MED / {len(low_traps)} LOW scope traps; "
        f"{weak_count} weak service-line fits; {high_impact_drivers} high-impact effort drivers."
    )
    rationale = f"Rubric v{rubric_version()} computed {score}/100 from: {deduction_notes}"
    if no_go_hits:
        rationale += f" NO_GO signals fired: {', '.join(no_go_hits)}."
    elif conditional_hits:
        rationale += f" Conditional signals fired: {', '.join(conditional_hits)}."

    confidence = "medium"
    if len([f for f in fits if f == "NOT_REQUESTED"]) >= 3:
        confidence = "low"

    return {
        "bid_fit_score": max(0, min(100, score)),
        "recommendation": recommendation,
        "rationale": rationale,
        "confidence": confidence,
        "no_go_signal_ids": no_go_hits,
        "conditional_signal_ids": conditional_hits,
    }
