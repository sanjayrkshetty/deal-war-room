"""Four-stage analysis pipeline (`dwr/pipeline.py`).

Stage 0 PRE-FLIGHT  (code)   re-verify scrub state, load clause map
Stage 1 TRIAGE      (LLM-S)  batch relevance/topic/service-line tagging
Stage 2 RISK PASS   (LLM-L)  traps, effort drivers, gates, dates
Stage 3 SYNTHESIS   (LLM-L)  matrix, question bank, win themes
Stage 4 ENFORCEMENT (code)   citation validation + one bounded repair

The verdict is computed by dwr.scoring AFTER enforcement, from enforced
signals only. Malformed-JSON policy per stage: validate → one retry with the
error appended → clean stage failure.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections import defaultdict

from pydantic import ValidationError

from dwr.config import get_settings
from dwr.enforce import build_clause_map, enforce_claims
from dwr.llm import UNTRUSTED_DATA_RULE, GroqClient, GroqJSONError
from dwr.schemas import (
    TOPIC_PRIORITIES,
    VALID_SERVICE_LINES,
    VALID_TOPICS,
    BriefDraft,
    RiskOutput,
    TriageOutput,
    schema_hint,
)
from dwr.scrubber import is_clean_text
from dwr.scoring import compute_verdict, rubric_version

PIPELINE_VERSION = "1.0.0"

TRIAGE_BATCH_SIZE = 10
RISK_CHAR_BUDGET = 24_000


class PipelineError(RuntimeError):
    pass


def _stage_call(client: GroqClient, *, model: str, system: str, user: str, stage: str) -> dict:
    try:
        return client.chat_json(stage=stage, system=system, user=user, model=model)
    except GroqJSONError as exc:
        retry_user = (
            f"{user}\n\nYour previous reply was invalid: {exc}. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        return client.chat_json(stage=f"{stage}:retry", system=system, user=retry_user, model=model)


def _stage_validated(client: GroqClient, *, model: str, system: str, user: str, stage: str, schema):
    raw = _stage_call(client, model=model, system=system, user=user, stage=stage)
    try:
        return schema.model_validate(raw)
    except ValidationError as exc:
        retry_user = (
            f"{user}\n\nYour previous reply failed schema validation:\n{exc}\n"
            "Fix the issues and return ONLY a valid JSON object matching the schema. "
            "Include every required key — use an empty list [] for sections with no items."
        )
        raw2 = _stage_call(client, model=model, system=system, user=retry_user, stage=f"{stage}:schema-retry")
        try:
            return schema.model_validate(raw2)
        except ValidationError as exc2:
            raise PipelineError(f"{stage} output failed validation after retry: {exc2}") from exc2


def _clause_blocks(clauses: list) -> str:
    parts = [
        f'<clause id="{row["id"]}" ref="{row["clause_ref"]}">\n{row["body"]}\n</clause>'
        for row in clauses
    ]
    return "\n".join(parts)


def run_triage(client: GroqClient, clause_rows: list) -> tuple[dict[int, dict], int]:
    settings = get_settings()
    relevant: dict[int, dict] = {}
    dropped = 0
    system = (
        f"{UNTRUSTED_DATA_RULE}\nTag each clause for a security-services bid review. "
        f"topics values must come from {sorted(VALID_TOPICS)}; service_lines values from "
        f'{sorted(VALID_SERVICE_LINES)} (empty list if none). Return JSON matching: '
        f"{schema_hint(TriageOutput)}"
    )
    for offset in range(0, len(clause_rows), TRIAGE_BATCH_SIZE):
        batch = clause_rows[offset : offset + TRIAGE_BATCH_SIZE]
        user = f"<tender>\n{_clause_blocks(batch)}\n</tender>"
        parsed = _stage_validated(
            client,
            model=settings.model_triage,
            system=system,
            user=user,
            stage="triage",
            schema=TriageOutput,
        )
        by_id = {c.clause_id: c for c in parsed.clauses}
        for row in batch:
            tag = by_id.get(row["id"])
            if tag is None or not tag.relevant:
                dropped += 1
                continue
            topics = [t for t in tag.topics if t in VALID_TOPICS] or ["other"]
            lines = [s for s in tag.service_lines if s in VALID_SERVICE_LINES]
            relevant[row["id"]] = {
                "topics": topics,
                "service_lines": lines,
                "summary": tag.summary,
            }
    return relevant, dropped


def _select_within_budget(relevant_ids: set[int], clause_rows: list) -> tuple[list, int]:
    rank = {topic: i for i, topic in enumerate(TOPIC_PRIORITIES)}

    def priority_of(row) -> int:
        topics = relevant_ids.get(row["id"], {}).get("topics", ["other"])
        return min((rank.get(t, 99) for t in topics), default=99)

    ordered = sorted(clause_rows, key=priority_of)
    selected: list = []
    used = 0
    for row in ordered:
        cost = len(row["body"])
        if used + cost > RISK_CHAR_BUDGET:
            continue
        selected.append(row)
        used += cost
    return selected, len(ordered) - len(selected)


def run_risk_pass(client: GroqClient, clause_rows: list) -> RiskOutput:
    settings = get_settings()
    system = (
        f"{UNTRUSTED_DATA_RULE}\nIdentify bid-shaping signals for a cybersecurity services "
        "vendor: scope traps (vague acceptance criteria, unlimited support or effort language, "
        "liquidated damages, asymmetric liability), effort drivers, eligibility gates "
        "(certifications, turnover, authorizations), key dates (submission deadline, pre-bid "
        "meeting, Q&A cutoff). Every evidence quoted_span MUST be verbatim (>=40 chars / >=8 "
        f"words) from its cited clause id. Return JSON matching: {schema_hint(RiskOutput)}"
    )
    user = f"<tender>\n{_clause_blocks(clause_rows)}\n</tender>"
    return _stage_validated(
        client,
        model=settings.model_synthesis,
        system=system,
        user=user,
        stage="risk",
        schema=RiskOutput,
    )


def run_synthesis(client: GroqClient, relevant: dict[int, dict], risk: RiskOutput) -> BriefDraft:
    settings = get_settings()
    context_lines = [
        f'<clause id="{cid}" topics="{",".join(tag["topics"])}" lines="{",".join(tag["service_lines"])}">{tag["summary"]}</clause>'
        for cid, tag in sorted(relevant.items())
    ]
    risk_digest = json.dumps(risk.model_dump(), separators=(",", ":"))[:8000]
    system = (
        f"{UNTRUSTED_DATA_RULE}\nBuild the analyst sections of a Deal Decision Brief: "
        "service_line_matrix (fit ratings DFIR/VAPT/GRC/SOC/RED_TEAM with evidence_refs), "
        "question_bank, win_themes (max 25 words each). NEVER output numeric scores or "
        "GO/NO_GO recommendations - those are computed elsewhere. Quote verbatim spans "
        f"(>=40 chars / >=8 words) from cited clause ids. Return JSON matching: "
        f"{schema_hint(BriefDraft)}"
    )
    user = (
        f"<tender-clause-index>\n{chr(10).join(context_lines)}\n</tender-clause-index>\n"
        f"<validated-risk-signals>{risk_digest}</validated-risk-signals>"
    )
    return _stage_validated(
        client,
        model=settings.model_synthesis,
        system=system,
        user=user,
        stage="synthesis",
        schema=BriefDraft,
    )


def _sections_from(risk: RiskOutput, draft: BriefDraft) -> dict[str, list[dict]]:
    def evidence_list(model_items):
        return [item.model_dump() for item in model_items]

    sections: dict[str, list[dict]] = {
        "scope_traps": evidence_list(risk.scope_traps),
        "effort_drivers": evidence_list(risk.effort_drivers),
        "eligibility_gates": evidence_list(risk.eligibility_gates),
        "key_dates": evidence_list(risk.key_dates),
    }
    for fit in draft.service_line_matrix:
        entry = fit.model_dump()
        entry["evidence"] = entry.pop("evidence_refs")
        if entry["fit"] == "NOT_REQUESTED":
            entry["no_citation_required"] = True
        sections.setdefault("service_line_matrix", []).append(entry)
    sections["question_bank"] = evidence_list(draft.question_bank)
    sections["win_themes"] = evidence_list(draft.win_themes)
    return sections


def _repair_claims(
    client: GroqClient,
    failed_by_section: dict[str, list[tuple[int, dict, list[str]]]],
    clause_map: dict[int, str],
) -> dict[str, list[dict]]:
    """Returns {section_name: [{"index": int, ...fixed_item...}]}."""
    settings = get_settings()
    clause_context = "\n".join(
        f'<clause id="{cid}">{body[:1200]}</clause>' for cid, body in clause_map.items()
    )
    payload = {
        name: [
            {"index": index, **{k: v for k, v in item.items()},
             "validation_errors": errors}
            for index, item, errors in entries
        ]
        for name, entries in failed_by_section.items()
    }
    system = (
        f"{UNTRUSTED_DATA_RULE}\nFix rejected brief claims. Each entry below failed citation "
        "validation and includes its validation_errors plus an \"index\" field. Correct the "
        "clause_id and/or replace quoted_span with a VERBATIM span (>=40 chars / >=8 words) "
        "taken from the cited clause body only. Return JSON shaped like "
        '{"section_name": [{"index": <int>, ...fixed fields..., "evidence": [...]}]}. '
        'Omit entries you cannot fix.'
    )
    user = (
        f"<rejected-claims>{json.dumps(payload)}</rejected-claims>\n"
        f"<clauses>{clause_context}</clauses>"
    )
    raw = _stage_call(
        client,
        model=settings.model_synthesis,
        system=system,
        user=user,
        stage="repair",
    )
    fixed: dict[str, list[dict]] = {}
    for name, items in raw.items():
        if isinstance(items, list) and all(isinstance(i, dict) and "index" in i for i in items):
            fixed[name] = items
    return fixed


def _apply_repairs(
    sections: dict[str, list[dict]],
    repaired_raw: dict[str, list[dict]],
    clause_map: dict[int, str],
) -> None:
    for name, fixed_items in repaired_raw.items():
        target = sections.get(name)
        if target is None:
            continue
        for fixed in fixed_items:
            index = fixed.pop("index", None)
            if not isinstance(index, int) or index < 0 or index >= len(target):
                continue
            candidate = dict(target[index])
            candidate.update(fixed)
            ok, _, _, _errors = None, None, None, None
            from dwr.enforce import _validate_item_evidence

            passed, _, errs = _validate_item_evidence(candidate, f"{name}[{index}]", clause_map)
            if passed:
                target[index] = candidate


def run_pipeline(conn: sqlite3.Connection, doc_id: int, analysis_id: int) -> dict:
    def progress(stage: str) -> None:
        conn.execute(
            "UPDATE analyses SET status='running', stage=? WHERE id=?", (stage, analysis_id)
        )
        conn.commit()

    conn.execute("PRAGMA foreign_keys=ON")
    try:
        progress("preflight")
        doc = conn.execute(
            "SELECT scrubbed_text FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not doc:
            raise PipelineError(f"document {doc_id} not found")
        if not is_clean_text(doc["scrubbed_text"]):
            raise PipelineError("preflight failed: stored text fails clean-check")

        clause_rows = conn.execute(
            "SELECT id, clause_ref, heading, body FROM clauses WHERE doc_id = ? ORDER BY ordinal",
            (doc_id,),
        ).fetchall()
        if not clause_rows:
            raise PipelineError("document has no clauses; re-ingest or reindex first")
        clause_map = build_clause_map(clause_rows)

        client = GroqClient()

        progress("triage")
        relevant, triage_dropped = run_triage(client, clause_rows)

        progress("risk")
        relevant_rows = [row for row in clause_rows if row["id"] in relevant]
        selected, budget_dropped = _select_within_budget(relevant, relevant_rows)
        risk = run_risk_pass(client, selected)

        progress("synthesis")
        draft = run_synthesis(client, relevant, risk)

        progress("enforcement")
        sections = _sections_from(risk, draft)

        first_pass = enforce_claims(sections, clause_map)
        still_failing_paths = set(first_pass.dropped_paths)
        if still_failing_paths:
            failed_by_section: dict[str, list[tuple[int, dict, list[str]]]] = defaultdict(list)
            for section_name, items in sections.items():
                for index, item in enumerate(items):
                    path = f"{section_name}[{index}]"
                    if path in still_failing_paths:
                        errors = [e for e in first_pass.validation_errors if e.startswith(path)]
                        failed_by_section[section_name].append((index, item, errors))
            repaired_raw = _repair_claims(client, dict(failed_by_section), clause_map)
            _apply_repairs(sections, repaired_raw, clause_map)

        final_pass = enforce_claims(sections, clause_map)

        progress("scoring")

        def payload_of(section: str) -> list[dict]:
            return [
                {k: v for k, v in item.items() if k != "_section"}
                for item in final_pass.clean_items
                if item.get("_section") == section
            ]

        verdict = compute_verdict(
            risk_output={
                "scope_traps": payload_of("scope_traps"),
                "effort_drivers": payload_of("effort_drivers"),
            },
            brief_draft={"service_line_matrix": payload_of("service_line_matrix")},
            scrubbed_text=doc["scrubbed_text"],
        )

        payload_sections: dict[str, list[dict]] = {}
        for item in final_pass.clean_items:
            section_name = item["_section"]
            payload_sections.setdefault(section_name, []).append(
                {k: v for k, v in item.items() if k != "_section"}
            )

        meta = {
            "uncited_claims_count": final_pass.uncited_count,
            "dropped_clauses_count": triage_dropped + budget_dropped,
            "pipeline_version": PIPELINE_VERSION,
            "rubric_version": rubric_version(),
            "model_config": {
                "triage": get_settings().model_triage,
                "synthesis": get_settings().model_synthesis,
            },
        }

        brief_payload = {"verdict": verdict, **payload_sections, "meta": meta}

        cursor = conn.execute(
            """
            INSERT INTO briefs (analysis_id, bid_fit_score, recommendation, confidence,
                                payload_json, uncited_claims_count, dropped_clauses_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                verdict["bid_fit_score"],
                verdict["recommendation"],
                verdict["confidence"],
                json.dumps(brief_payload),
                final_pass.uncited_count,
                meta["dropped_clauses_count"],
            ),
        )
        brief_id = cursor.lastrowid

        seen: set[tuple] = set()
        citation_rows = []
        for c in final_pass.citations:
            key = (c["claim_path"], c["clause_id"])
            if key in seen:
                continue
            seen.add(key)
            citation_rows.append(
                (
                    brief_id,
                    c["claim_path"],
                    c["clause_id"],
                    c["quoted_span"],
                    c["span_start"],
                    c["span_end"],
                )
            )
        if citation_rows:
            conn.executemany(
                """
                INSERT OR IGNORE INTO citations
                    (brief_id, claim_path, clause_id, quoted_span, span_start, span_end)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                citation_rows,
            )

        conn.execute(
            "UPDATE analyses SET status='done', stage=NULL, finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (analysis_id,),
        )
        conn.commit()
        return {"analysis_id": analysis_id, "brief_id": brief_id, "verdict": verdict}

    except Exception as exc:
        conn.rollback()
        conn.execute(
            "UPDATE analyses SET status='failed', error=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (str(exc)[:500], analysis_id),
        )
        conn.commit()
        raise


def start_analysis(conn: sqlite3.Connection, doc_id: int) -> int:
    active = conn.execute(
        "SELECT id FROM analyses WHERE doc_id=? AND status IN ('queued','running')", (doc_id,)
    ).fetchone()
    if active:
        raise PipelineError(f"analysis {active['id']} already active for document {doc_id}")
    cursor = conn.execute(
        "INSERT INTO analyses (doc_id, status, pipeline_version) VALUES (?, 'queued', ?)",
        (doc_id, PIPELINE_VERSION),
    )
    conn.commit()
    return cursor.lastrowid


def launch_background(doc_id: int, analysis_id: int) -> threading.Thread:
    def worker() -> None:
        from dwr.db import connect

        thread_conn = connect()
        try:
            run_pipeline(thread_conn, doc_id, analysis_id)
        except Exception:
            pass
        finally:
            thread_conn.close()

    thread = threading.Thread(target=worker, name=f"dwr-analysis-{analysis_id}", daemon=True)
    thread.start()
    return thread
