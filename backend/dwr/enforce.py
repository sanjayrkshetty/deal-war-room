"""Citation enforcement (`dwr/enforce.py`).

The guarantee (PLAN.md Phase 3, critic B3/B4 spec):
  1. clause_id must exist in the document's clause map
  2. quoted_span must fuzzy-match the CITED clause body only
     (rapidfuzz partial_ratio >= 85, min 40 chars / 8 tokens)
  3. matching char offsets are persisted for UI highlighting
  4. exactly ONE repair round-trip, then failing claims are REMOVED from the
     payload and counted — never rendered uncited.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

MIN_SCORE = 85.0
MIN_SPAN_CHARS = 40
MIN_SPAN_TOKENS = 8


@dataclass
class EnforcementResult:
    clean_items: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    dropped_paths: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

    @property
    def uncited_count(self) -> int:
        return len(self.dropped_paths)


def validate_span(quoted_span: str, clause_body: str) -> tuple[bool, int | None, int | None, str | None]:
    span = " ".join(quoted_span.split())
    if len(span) < MIN_SPAN_CHARS or len(span.split()) < MIN_SPAN_TOKENS:
        return False, None, None, f"span too short ({len(span)} chars / {len(span.split())} tokens)"

    alignment = fuzz.partial_ratio_alignment(span, " ".join(clause_body.split()))
    if alignment is None or alignment.score < MIN_SCORE:
        return False, None, None, f"span not found in cited clause (score {alignment.score if alignment else 0:.0f})"
    return True, int(alignment.dest_start), int(alignment.dest_end), None


def _validate_item_evidence(item: dict, path: str, clause_map: dict[int, str]) -> tuple[bool, list[dict], list[str]]:
    citations: list[dict] = []
    errors: list[str] = []
    for position, ev in enumerate(item.get("evidence", [])):
        clause_id = ev.get("clause_id")
        body = clause_map.get(clause_id)
        if body is None:
            errors.append(f"{path}.evidence[{position}]: clause_id {clause_id} does not exist")
            continue
        ok, start, end, reason = validate_span(ev.get("quoted_span", ""), body)
        if not ok:
            errors.append(f"{path}.evidence[{position}]: {reason}")
            continue
        citations.append(
            {
                "claim_path": path,
                "clause_id": clause_id,
                "quoted_span": ev["quoted_span"],
                "span_start": start,
                "span_end": end,
            }
        )
    return (len(errors) == 0 and len(citations) > 0), citations, errors


def enforce_claims(
    sections: dict[str, list[dict]],
    clause_map: dict[int, str],
) -> EnforcementResult:
    result = EnforcementResult()
    for section_name, items in sections.items():
        for index, item in enumerate(items):
            path = f"{section_name}[{index}]"
            if item.get("no_citation_required"):
                clean = {k: v for k, v in item.items() if k not in ("evidence", "no_citation_required", "_section")}
                clean["clause_ids"] = []
                clean["_section"] = section_name
                result.clean_items.append(clean)
                continue
            ok, citations, errors = _validate_item_evidence(item, path, clause_map)
            if ok:
                clean = {k: v for k, v in item.items() if k != "evidence"}
                refs = [c["clause_id"] for c in citations]
                clean["clause_ids"] = sorted(set(refs))
                result.clean_items.append({**clean, "_section": section_name})
                result.citations.extend(citations)
            else:
                result.dropped_paths.append(path)
                result.validation_errors.extend(errors)
    return result


def build_clause_map(clauses: list) -> dict[int, str]:
    return {row["id"]: row["body"] for row in clauses}
