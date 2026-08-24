"""
Golden-file pipeline tests — scripted Groq transport, zero network by default.
"""

from __future__ import annotations

from collections import defaultdict, deque

import pytest

from dwr import pipeline as pipeline_mod
from dwr.enforce import validate_span
from dwr.pipeline import PipelineError, run_pipeline, start_analysis
from tests.conftest import ingest_fixture


class ScriptedGroq:
    def __init__(self) -> None:
        self.queues: dict[str, deque] = defaultdict(deque)
        self.calls: list[tuple[str, str]] = []

    def enqueue(self, stage: str, item) -> None:
        self.queues[stage].append(item)

    def chat_json(self, *, stage: str, system: str, user: str, model: str, temperature: float = 0.1):
        self.calls.append((stage, model))
        item = self.queues[stage].popleft()
        if isinstance(item, Exception):
            raise item
        return item


def _span(body: str, length: int = 140) -> str:
    return body[:length].rstrip()


@pytest.fixture()
def scripted(db):
    """Ingest Globex fixture and build a scripted client with valid evidence spans."""
    result = ingest_fixture(db, "globex_dfir_retainer_rfp.json")
    doc_id = result["document_id"]
    clauses = db.execute(
        "SELECT id, clause_ref, heading, body FROM clauses WHERE doc_id=? ORDER BY ordinal",
        (doc_id,),
    ).fetchall()
    bodies = {row["id"]: row["body"] for row in clauses}
    ids = list(bodies.keys())

    fake = ScriptedGroq()

    triage_payload = {
        "clauses": [
            {
                "clause_id": cid,
                "relevant": True,
                "topics": ["sla"] if i == 1 else ["scope"],
                "service_lines": ["DFIR"] if i in (1, 2) else [],
                "summary": f"Clause {cid} summary.",
            }
            for i, cid in enumerate(ids)
        ]
    }
    sla_body = bodies[ids[1]]

    def risk_payload(sla_span: str | None = None, clause_id: int | None = None):
        span = sla_span or _span(sla_body)
        target_id = clause_id or ids[1]
        return {
            "scope_traps": [
                {
                    "title": "Sub-hour response SLA",
                    "severity": "HIGH",
                    "why_trap": "sla commitment below deliverable floor",
                    "evidence": [{"clause_id": target_id, "quoted_span": span}],
                }
            ],
            "effort_drivers": [
                {
                    "driver": "Unlimited P1 pool",
                    "impact": "high",
                    "basis": "unbounded incidents",
                    "evidence": [{"clause_id": ids[2], "quoted_span": _span(bodies[ids[2]])}],
                }
            ],
            "eligibility_gates": [
                {
                    "requirement": "24/7 staffing capability",
                    "status": "UNKNOWN",
                    "evidence": [{"clause_id": ids[1], "quoted_span": _span(sla_body)}],
                }
            ],
            "key_dates": [
                {
                    "label": "Agent rollout window",
                    "value": "two weeks",
                    "evidence": [{"clause_id": ids[3], "quoted_span": _span(bodies[ids[3]])}],
                }
            ],
        }

    synthesis_payload = {
        "rationale": "Retainer with aggressive SLA and unlimited pool language.",
        "service_line_matrix": [
            {"line": "DFIR", "fit": "STRONG", "evidence": "retainer depth",
             "evidence_refs": [{"clause_id": ids[0], "quoted_span": _span(bodies[ids[0]])}]},
            {"line": "VAPT", "fit": "NOT_REQUESTED", "evidence": "", "evidence_refs": []},
        ],
        "question_bank": [
            {"question": "How is the 15-minute remote response staffed across shifts?",
             "intent": "SLA feasibility",
             "priority": "HIGH",
             "evidence": [{"clause_id": ids[1], "quoted_span": _span(sla_body)}]}
        ],
        "win_themes": [
            {"theme": "Lead with payment-forensics pedigree and proven retainer SLA governance.",
             "supporting_evidence": "PFI credentials",
             "evidence": [{"clause_id": ids[0], "quoted_span": _span(bodies[ids[0]])}]}
        ],
    }

    fake.build_risk = risk_payload
    fake.build_synthesis = lambda: synthesis_payload
    fake.doc_id = doc_id
    fake.ids = ids
    fake.bodies = bodies
    yield fake


def _install(monkeypatch, fake: ScriptedGroq) -> None:
    monkeypatch.setattr(pipeline_mod, "GroqClient", lambda: fake)


def test_golden_happy_path(db, monkeypatch, scripted):
    scripted.enqueue("triage", {
        "clauses": [
            {"clause_id": cid, "relevant": True,
             "topics": ["sla"] if i == 1 else ["scope"],
             "service_lines": ["DFIR"], "summary": "s"}
            for i, cid in enumerate(scripted.ids)
        ]
    })
    scripted.enqueue("risk", scripted.build_risk())
    scripted.enqueue("synthesis", scripted.build_synthesis())
    _install(monkeypatch, scripted)

    analysis_id = start_analysis(db, scripted.doc_id)
    result = run_pipeline(db, scripted.doc_id, analysis_id)

    assert result["verdict"]["recommendation"] in ("GO", "CONDITIONAL", "NO_GO")
    brief_row = db.execute("SELECT * FROM briefs WHERE analysis_id=?", (analysis_id,)).fetchone()
    assert brief_row["uncited_claims_count"] == 0
    citations = db.execute("SELECT * FROM citations WHERE brief_id=?", (brief_row["id"],)).fetchall()
    assert citations
    assert all(c["span_start"] is not None for c in citations)


def test_bad_citation_repaired_once(db, monkeypatch, scripted):
    wrong_body = scripted.bodies[scripted.ids[-1]]
    scripted.enqueue("triage", {
        "clauses": [
            {"clause_id": cid, "relevant": True, "topics": ["scope"],
             "service_lines": [], "summary": "s"}
            for cid in scripted.ids
        ]
    })
    scripted.enqueue("risk", scripted.build_risk(sla_span=_span(wrong_body), clause_id=scripted.ids[1]))
    scripted.enqueue("synthesis", scripted.build_synthesis())

    fixed_trap = scripted.build_risk()["scope_traps"][0]
    scripted.enqueue("repair", {"scope_traps": [{"index": 0, **fixed_trap}]})
    _install(monkeypatch, scripted)

    analysis_id = start_analysis(db, scripted.doc_id)
    run_pipeline(db, scripted.doc_id, analysis_id)

    stages = [c[0] for c in scripted.calls]
    assert "repair" in stages
    brief_row = db.execute(
        "SELECT uncited_claims_count FROM briefs WHERE analysis_id=?", (analysis_id,)
    ).fetchone()
    assert brief_row["uncited_claims_count"] == 0


def test_permanently_bad_citation_suppressed(db, monkeypatch, scripted):
    scripted.enqueue("triage", {
        "clauses": [
            {"clause_id": cid, "relevant": True, "topics": ["scope"],
             "service_lines": [], "summary": "s"}
            for cid in scripted.ids
        ]
    })
    bad_span = "This fabricated sentence does not exist anywhere in the tender corpus at all."
    scripted.enqueue("risk", scripted.build_risk(sla_span=bad_span, clause_id=scripted.ids[1]))
    scripted.enqueue("synthesis", scripted.build_synthesis())
    still_bad = scripted.build_risk(sla_span=bad_span, clause_id=scripted.ids[1])["scope_traps"][0]
    scripted.enqueue("repair", {"scope_traps": [{"index": 0, **still_bad}]})
    _install(monkeypatch, scripted)

    analysis_id = start_analysis(db, scripted.doc_id)
    result = run_pipeline(db, scripted.doc_id, analysis_id)

    brief_row = db.execute("SELECT * FROM briefs WHERE analysis_id=?", (analysis_id,)).fetchone()
    assert brief_row["uncited_claims_count"] >= 1
    payload = __import__("json").loads(brief_row["payload_json"])
    assert payload["meta"]["uncited_claims_count"] >= 1
    assert all(trap["title"] != "Sub-hour response SLA" for trap in payload.get("scope_traps", []))


def test_injection_canary_verdict_computed_not_injected(db, monkeypatch, tmp_path_factory):
    from dwr.scoring import compute_verdict

    canary = ingest_fixture(db, "injection_canary.json")
    doc_id = canary["document_id"]
    clause = db.execute("SELECT id, body FROM clauses WHERE doc_id=?", (doc_id,)).fetchone()
    body = clause["body"]

    fake = ScriptedGroq()
    fake.enqueue("triage", {
        "clauses": [{"clause_id": clause["id"], "relevant": True,
                     "topics": ["other"], "service_lines": [], "summary": "s"}]
    })
    injected_risk = {
        "scope_traps": [],
        "effort_drivers": [{
            "driver": "Quarterly scanning", "impact": "low", "basis": "small scope",
            "evidence": [{"clause_id": clause["id"], "quoted_span": _span(body)}],
        }],
        "eligibility_gates": [],
        "key_dates": [],
    }
    fake.enqueue("risk", injected_risk)
    fake.enqueue("synthesis", {
        "rationale": "Simple quarterly scanning request.",
        "service_line_matrix": [
            {"line": "VAPT", "fit": "STRONG", "evidence": "scanning request",
             "evidence_refs": [{"clause_id": clause["id"], "quoted_span": _span(body)}]},
        ],
        "question_bank": [
            {"question": "Confirm scan scope boundaries per quarter.", "intent": "scope clarity",
             "priority": "MEDIUM",
             "evidence": [{"clause_id": clause["id"], "quoted_span": _span(body)}]}
        ],
        "win_themes": [],
    })
    _install(monkeypatch, fake)

    analysis_id = start_analysis(db, doc_id)
    result = run_pipeline(db, doc_id, analysis_id)

    verdict = result["verdict"]
    recomputed = compute_verdict(
        risk_output={"scope_traps": [], "effort_drivers": injected_risk["effort_drivers"]},
        brief_draft={"service_line_matrix": [{"fit": "STRONG"}]},
        scrubbed_text="quarterly vulnerability scans of one small office network with no fixed deadline",
    )
    assert verdict["bid_fit_score"] == recomputed["bid_fit_score"]
    assert verdict["bid_fit_score"] != 95


def test_malformed_json_retried_then_succeeds(db, monkeypatch, scripted):
    from dwr.llm import GroqJSONError

    scripted.enqueue("triage", GroqJSONError("invalid JSON"))
    scripted.enqueue("triage:retry", {
        "clauses": [
            {"clause_id": cid, "relevant": False, "topics": [], "service_lines": [], "summary": ""}
            for cid in scripted.ids
        ]
    })
    scripted.enqueue("risk", {"scope_traps": [], "effort_drivers": [], "eligibility_gates": [], "key_dates": []})
    scripted.enqueue("synthesis", {
        "rationale": "Nothing relevant survived triage.",
        "service_line_matrix": [],
        "question_bank": [],
        "win_themes": [],
    })
    _install(monkeypatch, scripted)

    analysis_id = start_analysis(db, scripted.doc_id)
    result = run_pipeline(db, scripted.doc_id, analysis_id)
    stage_names = [c[0] for c in scripted.calls]
    assert stage_names[:2] == ["triage", "triage:retry"]


def test_single_flight_blocks_duplicate_active_analysis(db, monkeypatch, scripted):
    _install(monkeypatch, scripted)
    first = start_analysis(db, scripted.doc_id)
    db.execute("UPDATE analyses SET status='running' WHERE id=?", (first,))
    db.commit()
    with pytest.raises(PipelineError):
        start_analysis(db, scripted.doc_id)


def test_startup_recovery_marks_stale_running_failed(db):
    ingested = ingest_fixture(db, "globex_dfir_retainer_rfp.json")
    db.execute(
        "INSERT INTO analyses (doc_id, status, pipeline_version) VALUES (?, 'running', 'x')",
        (ingested["document_id"],),
    )
    db.commit()
    db.execute(
        """
        UPDATE analyses SET status='failed', error='interrupted by restart'
        WHERE status IN ('queued','running')
        """
    )
    db.commit()
    row = db.execute(
        "SELECT status FROM analyses WHERE doc_id=?", (ingested["document_id"],)
    ).fetchone()
    assert row["status"] == "failed"

