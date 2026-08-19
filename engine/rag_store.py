"""
Local RAG Vector Store & Memory Bank (`engine/rag_store.py`)

Provides local vector search over anonymized proposal chunks stored in SQLite.
Guarantees fallback to built-in cybersecurity frameworks (SANS DFIR, OWASP, ISO 27001, NIST)
when database matches have low search relevance.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import TypedDict, Optional

from engine.scrubber import scrub_text

_DB_PATH = Path("corpus/scrubbed/presales_intelligence.db")


class MemoryChunk(TypedDict):
    id: int
    bu_tag: str
    service_line: str
    title: str
    content: str
    score: float
    is_fallback: bool


# Built-in Cybersecurity Framework Templates for Fallback
_BUILTIN_FRAMEWORKS = {
    "dfir_ca": {
        "title": "SANS Compromise Assessment (CA) Framework",
        "content": (
            "Scope: Endpoint IOC sweeps, active threat hunting, memory forensics, and C2 traffic analysis. "
            "Deliverables: Compromise Assessment Report, Indicator of Compromise (IOC) inventory, "
            "and immediate threat containment recommendations. Methodology aligned with SANS Incident Handling Guide."
        ),
    },
    "dfir_bas": {
        "title": "Breach & Attack Simulation (BAS) Framework",
        "content": (
            "Scope: Automated attack vector simulation, atomic red team tests across MITRE ATT&CK matrix, "
            "and continuous SIEM/EDR detection rule validation. Deliverables: ATT&CK Coverage Matrix, "
            "Detection Gap Analysis, and Rule Optimization Guidance."
        ),
    },
    "dfir_ifi": {
        "title": "Incident Forensics & Investigation (IFI) Framework",
        "content": (
            "Scope: Active breach containment, digital evidence acquisition under chain of custody, "
            "root cause analysis, and malware reverse engineering. Deliverables: Digital Forensics Investigation Report, "
            "Timeline Analysis, and Remediation Roadmap."
        ),
    },
    "dfir_retainer": {
        "title": "DFIR Emergency Response Retainer SLA",
        "content": (
            "Scope: 24/7 SLA guaranteed emergency incident response (2-hour remote, 4-hour on-site), "
            "prepaid incident response hours pool, and annual incident readiness tabletop exercise. "
            "Deliverables: Emergency Escalation Matrix, Retainer Service Level Agreement, and Incident Playbooks."
        ),
    },
    "vapt": {
        "title": "OWASP & PTES Vulnerability Assessment & Pentesting",
        "content": (
            "Scope: Web application security testing (OWASP Top 10), API security review, "
            "external/internal network pentesting, and cloud configuration assessment. "
            "Deliverables: Technical Vulnerability Report, Executive Risk Summary, and Re-testing Validation."
        ),
    },
    "grc": {
        "title": "ISO 27001:2022 & PCI-DSS 4.0 Compliance Audit Framework",
        "content": (
            "Scope: Gap analysis against ISO 27001 Annex A controls, PCI-DSS 4.0 requirement verification, "
            "SOC 2 Type II audit readiness, and vendor risk management framework evaluation. "
            "Deliverables: Compliance Readiness Roadmap, Control Gap Matrix, and Executive Risk Briefing."
        ),
    },
    "soc": {
        "title": "24/7 Managed SOC & SIEM/EDR Onboarding Framework",
        "content": (
            "Scope: SIEM log source ingestion sizing (Events Per Second / GB per day), EDR agent deployment, "
            "L1/L2 analyst escalation workflows, and custom detection rule tuning. "
            "Deliverables: SOC Operations Runbook, Log Ingestion Scope, and SLA Matrix."
        ),
    },
}


def _compute_keyword_vector(text: str) -> dict[str, float]:
    """Generates simple normalized term frequency vector for local similarity calculation."""
    words = re.findall(r'\w+', text.lower())
    if not words:
        return {}
    tf: dict[str, float] = {}
    for word in words:
        tf[word] = tf.get(word, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in tf.values()))
    if norm > 0:
        for k in tf:
            tf[k] /= norm
    return tf


def _cosine_similarity(vec1: dict[str, float], vec2: dict[str, float]) -> float:
    """Computes cosine similarity between two term-frequency vectors."""
    dot = sum(val * vec2.get(k, 0.0) for k, val in vec1.items())
    return float(dot)


class RAGStore:
    def __init__(self, db_path: Path | str = _DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the SQLite schema for scrubbed memory chunks."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scrubbed_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bu_tag TEXT NOT NULL,
                    service_line TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

    def add_chunk(self, bu_tag: str, service_line: str, title: str, content: str) -> int:
        """
        Sanitizes text via DLP scrubber and inserts it into the Scrubbed Database.
        """
        scrubbed_content = scrub_text(content)
        vec = _compute_keyword_vector(f"{title} {scrubbed_content}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scrubbed_chunks (bu_tag, service_line, title, content, vector_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (bu_tag.lower(), service_line.lower(), title, scrubbed_content, json.dumps(vec)),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def search_memory(
        self,
        query: str,
        bu_tag: Optional[str] = None,
        service_line: Optional[str] = None,
        top_k: int = 3,
    ) -> list[MemoryChunk]:
        """
        Searches scrubbed database for query relevance.
        Falls back to built-in cybersecurity framework templates if DB relevance is low.
        """
        query_vec = _compute_keyword_vector(query)
        results: list[MemoryChunk] = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = "SELECT * FROM scrubbed_chunks"
            params: list[str] = []
            conditions: list[str] = []

            if bu_tag:
                conditions.append("bu_tag = ?")
                params.append(bu_tag.lower())
            if service_line:
                conditions.append("service_line = ?")
                params.append(service_line.lower())

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            rows = cursor.execute(sql, params).fetchall()

            for row in rows:
                vec = json.loads(row["vector_json"])
                sim = _cosine_similarity(query_vec, vec)
                results.append(
                    {
                        "id": row["id"],
                        "bu_tag": row["bu_tag"],
                        "service_line": row["service_line"],
                        "title": row["title"],
                        "content": row["content"],
                        "score": round(sim, 4),
                        "is_fallback": False,
                    }
                )

        # Sort by similarity score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        # High relevance matches found in DB
        if results and results[0]["score"] >= 0.15:
            return results[:top_k]

        # Grounding Fallback: Return built-in framework template if DB relevance is low
        key = f"{bu_tag or 'dfir'}_{service_line or 'ca'}".lower()
        if key not in _BUILTIN_FRAMEWORKS:
            key = f"{bu_tag or 'vapt'}".lower()
            if key not in _BUILTIN_FRAMEWORKS:
                key = "dfir_ca"

        fw = _BUILTIN_FRAMEWORKS.get(key, _BUILTIN_FRAMEWORKS["dfir_ca"])

        fallback_chunk: MemoryChunk = {
            "id": -1,
            "bu_tag": bu_tag or "dfir",
            "service_line": service_line or "ca",
            "title": fw["title"],
            "content": fw["content"],
            "score": 1.0,
            "is_fallback": True,
        }

        # Return DB results prepended with fallback framework
        return [fallback_chunk] + results[: top_k - 1]
