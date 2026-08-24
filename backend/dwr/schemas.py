"""Brief payload schemas (`dwr/schemas.py`).

Single source of truth: LLM stages receive JSON hints derived from these
models and every response is re-validated against them. The numeric verdict
NEVER passes through an LLM — it is computed by dwr.scoring.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Severity = Literal["HIGH", "MED", "LOW"]
ServiceLine = Literal["DFIR", "VAPT", "GRC", "SOC", "RED_TEAM"]
Fit = Literal["STRONG", "PARTIAL", "WEAK", "NOT_REQUESTED"]
GateStatus = Literal["MET", "UNMET", "UNKNOWN"]
Priority = Literal["HIGH", "MEDIUM", "LOW"]


class QuotedEvidence(BaseModel):
    clause_id: int = Field(ge=1)
    quoted_span: str = Field(min_length=40, max_length=600)


class TriageClause(BaseModel):
    clause_id: int
    relevant: bool
    topics: list[str] = Field(default_factory=list)
    service_lines: list[str] = Field(default_factory=list)
    summary: str = ""


class TriageOutput(BaseModel):
    clauses: list[TriageClause]


class ScopeTrap(BaseModel):
    title: str = Field(max_length=140)
    severity: Severity
    why_trap: str
    evidence: list[QuotedEvidence] = Field(min_length=1)


class EffortDriver(BaseModel):
    driver: str = Field(max_length=140)
    impact: str
    basis: str
    evidence: list[QuotedEvidence] = Field(min_length=1)


class EligibilityGate(BaseModel):
    requirement: str
    status: GateStatus
    evidence: list[QuotedEvidence] = Field(min_length=1)


class KeyDate(BaseModel):
    label: str
    value: str
    evidence: list[QuotedEvidence] = Field(min_length=1)


class RiskOutput(BaseModel):
    scope_traps: list[ScopeTrap] = Field(default_factory=list)
    effort_drivers: list[EffortDriver] = Field(default_factory=list)
    eligibility_gates: list[EligibilityGate] = Field(default_factory=list)
    key_dates: list[KeyDate] = Field(default_factory=list)


class ServiceLineFit(BaseModel):
    line: ServiceLine
    fit: Fit
    evidence: str
    evidence_refs: list[QuotedEvidence] = Field(default_factory=list)


class QuestionItem(BaseModel):
    question: str
    intent: str
    priority: Priority
    evidence: list[QuotedEvidence] = Field(min_length=1)


class WinTheme(BaseModel):
    theme: str = Field(max_length=200)
    supporting_evidence: str
    evidence: list[QuotedEvidence] = Field(min_length=1)

    @field_validator("theme")
    @classmethod
    def max_25_words(cls, v: str) -> str:
        if len(v.split()) > 25:
            raise ValueError("win theme exceeds 25 words (anti-drafting guard)")
        return v


class BriefDraft(BaseModel):
    rationale: str = Field(default="", max_length=1200)
    service_line_matrix: list[ServiceLineFit] = Field(default_factory=list)
    question_bank: list[QuestionItem] = Field(default_factory=list)
    win_themes: list[WinTheme] = Field(default_factory=list)


TOPIC_PRIORITIES = [
    "sla",
    "penalty",
    "scope",
    "acceptance",
    "timeline",
    "compliance",
    "staffing",
    "pricing",
]

VALID_TOPICS = set(TOPIC_PRIORITIES) | {"other"}
VALID_SERVICE_LINES = {"DFIR", "VAPT", "GRC", "SOC", "RED_TEAM"}


class RepairRequest(BaseModel):
    errors: list[str]


def schema_hint(model_cls: type[BaseModel]) -> str:
    import json

    return json.dumps(model_cls.model_json_schema(), separators=(",", ":"))
