"""
Grounded Word Document (.docx) Proposal Exporter (`engine/docx_exporter.py`)

Creates structured, professional proposal documents ready for download,
incorporating executive summaries, service line scope breakdowns, and grounded citations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict, Any
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


class ProposalDocData(TypedDict):
    opportunity_name: str
    client_name_placeholder: str
    executive_summary: str
    service_lines: dict[str, str]
    methodology: str
    assumptions: list[str]
    timeline_weeks: int


def export_proposal_docx(data: ProposalDocData, target_file: Path | str) -> Path:
    """
    Generates an editable .docx proposal document.
    """
    target_path = Path(target_file)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # Configure Margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Document Header Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("CYBERSECURITY & PROPOSAL DOSSIER")
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = RGBColor(14, 165, 233)  # Teal Accent

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = subtitle.add_run(f"Prepared for: {data.get('client_name_placeholder', '[CLIENT_NAME]')}\n")
    sub_run.font.size = Pt(14)
    sub_run.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph().paragraph_format.space_after = Pt(24)

    # Executive Summary Section
    h1 = doc.add_heading("1. Executive Summary", level=1)
    doc.add_paragraph(data.get("executive_summary", "Executive summary for the technical proposal."))

    # Technical Scope Section
    h2 = doc.add_heading("2. Technical Scope of Work", level=1)

    service_lines = data.get("service_lines", {})
    if service_lines:
        for name, desc in service_lines.items():
            doc.add_heading(f"2.{list(service_lines.keys()).index(name) + 1} {name.upper()}", level=2)
            doc.add_paragraph(desc)
    else:
        doc.add_paragraph("Technical scope details aligned with SANS, OWASP, and ISO frameworks.")

    # Methodology
    doc.add_heading("3. Delivery Methodology", level=1)
    doc.add_paragraph(data.get("methodology", "Standard multi-phase assessment and reporting methodology."))

    # Project Timeline
    doc.add_heading("4. Estimated Project Timeline", level=1)
    doc.add_paragraph(f"The estimated execution duration is {data.get('timeline_weeks', 4)} weeks from project kickoff.")

    # Key Assumptions & Prerequisites
    doc.add_heading("5. Key Assumptions & Prerequisites", level=1)
    assumptions = data.get("assumptions", [])
    if assumptions:
        for item in assumptions:
            doc.add_paragraph(f"• {item}")
    else:
        doc.add_paragraph("• Timely access to scope systems, point of contact availability, and approved testing windows.")

    doc.save(target_path)
    return target_path
