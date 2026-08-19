"""
One-Time Offline Ingestion & DLP Sanitization Script (`scrub_and_ingest.py`)

Reads sample proposal documents, passes all text through `scrub_text()` to redact
all client identifiers, employer names, credentials, and pricing, and populates
the local anonymized database (`presales_intelligence.db`).

Zero live OneDrive dependency at application runtime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from engine.scrubber import scrub_text
from engine.rag_store import RAGStore


def seed_default_scrubbed_memories(rag: RAGStore) -> None:
    """Populates the database with initial anonymized security proposal templates."""
    print("Populating anonymized security proposal memory templates...")

    templates = [
        # DFIR - Compromise Assessment
        (
            "dfir",
            "ca",
            "Compromise Assessment Scoping Template",
            "Technical Scope: Endpoint IOC sweeps across domain hosts, memory artifact analysis, "
            "network threat hunting, and C2 beacon detection. Deliverables: Compromise Assessment Dossier, "
            "Threat Artifact Inventory, and Escalation Playbook. Aligned with SANS Incident Response standards."
        ),
        # DFIR - Breach & Attack Simulation
        (
            "dfir",
            "bas",
            "Breach & Attack Simulation Scoping Template",
            "Technical Scope: Automated MITRE ATT&CK technique execution, SIEM/EDR detection rule gap analysis, "
            "atomic red team test sweeps, and perimeter defense validation. Deliverables: ATT&CK Gap Matrix and Rule Tuning Guide."
        ),
        # DFIR - Incident Forensics
        (
            "dfir",
            "ifi",
            "Incident Forensics & Investigation Template",
            "Technical Scope: Live breach containment, forensic disk & memory image acquisition under chain of custody, "
            "reverse engineering of malicious binaries, and root cause timeline analysis. Deliverables: Digital Forensics Report."
        ),
        # DFIR - Retainer SLA
        (
            "dfir",
            "retainer",
            "DFIR Emergency Response Retainer SLA Template",
            "Technical Scope: 24/7 SLA guaranteed incident response (2-hour remote / 4-hour on-site), prepaid incident "
            "response hours pool, annual tabletop exercise, and quarterly incident readiness reviews."
        ),
        # VAPT - Pentest
        (
            "vapt",
            "vapt_pentest",
            "Vulnerability Assessment & Pentesting Template",
            "Technical Scope: OWASP Top 10 web application testing, REST/GraphQL API security review, external and internal "
            "infrastructure pentesting, and AWS/Azure cloud security posture review. Deliverables: VAPT Report & Re-test Validation."
        ),
        # GRC - Compliance Audit
        (
            "grc",
            "grc_audit",
            "ISO 27001 & PCI-DSS 4.0 Compliance Audit Template",
            "Technical Scope: ISO 27001:2022 Annex A control gap assessment, PCI-DSS 4.0 requirements audit, SOC 2 Type II "
            "readiness review, and third-party vendor risk framework drafting. Deliverables: Executive Control Gap Matrix."
        ),
        # SOC - Managed SOC Sizing
        (
            "soc",
            "managed_soc",
            "24/7 Managed SOC & SIEM Sizing Template",
            "Technical Scope: Log ingestion EPS/GB sizing, EDR agent deployment, L1/L2 incident escalation runbooks, "
            "and custom SIEM correlation rule tuning. Deliverables: SOC Operations Playbook."
        ),
    ]

    for bu_tag, service_line, title, content in templates:
        rag.add_chunk(bu_tag, service_line, title, content)

    print("[OK] Seed anonymized memory templates successfully created!")


def ingest_from_onedrive_if_available(rag: RAGStore) -> None:
    """Optionally ingests files from OneDrive path if available, scrubbing 100% of PII locally."""
    onedrive_path = Path(r"C:\Users\SISASanjayShetty\OneDrive - SISA Information Security Pvt. Ltd\Desktop\proposals")

    if not onedrive_path.exists():
        print(f"Note: OneDrive source path '{onedrive_path}' not present. Skipping OneDrive scan.")
        return

    print(f"Scanning raw files from '{onedrive_path}' for ONE-TIME OFFLINE SCRUBBED ingestion...")
    count = 0
    for root, _, files in os.walk(onedrive_path):
        for file in files:
            if file.endswith((".txt", ".md", ".docx")):
                file_path = Path(root) / file
                try:
                    text = ""
                    if file.endswith((".txt", ".md")):
                        text = file_path.read_text(encoding="utf-8", errors="ignore")
                    elif file.endswith(".docx"):
                        from docx import Document
                        doc = Document(file_path)
                        text = "\n".join([p.text for p in doc.paragraphs])

                    if text.strip():
                        # DLP Sanitization BEFORE saving to DB
                        scrubbed = scrub_text(text[:3000])  # Take first 3k chars
                        bu = "dfir" if "dfir" in file.lower() else ("vapt" if "vapt" in file.lower() else "grc")
                        rag.add_chunk(bu, "general", f"Scrubbed Proposal Template: {file}", scrubbed)
                        count += 1
                except Exception as err:
                    print(f"Warning: Could not process {file}: {err}")

    print(f"[OK] Ingested and scrubbed {count} files from OneDrive into local database!")


def main() -> None:
    print("==================================================================")
    print("PRESALES INTELLIGENCE - ONE-TIME OFFLINE SCRUBBED INGESTION")
    print("==================================================================")

    rag = RAGStore()

    # 1. Populate default anonymized seed memory templates
    seed_default_scrubbed_memories(rag)

    # 2. Ingest & scrub raw files if available locally
    ingest_from_onedrive_if_available(rag)

    print("\nDatabase initialization complete! App is ready for 100% offline or live demo run.")


if __name__ == "__main__":
    main()
