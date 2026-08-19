"""
Unit Tests for Presales Agent Engine (`tests/test_agents.py`)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.agents import PresalesAgentEngine


def test_strategic_deal_consultant():
    engine = PresalesAgentEngine()
    rfp = "Acme Corp requires a 24/7 DFIR retainer with 2-hour SLA and annual Compromise Assessment."

    deal = engine.run_strategic_deal_consultant(rfp)
    assert deal["win_probability"] > 0
    assert deal["deal_recommendation"] in ["RECOMMENDED", "CONDITIONAL_GO", "NO_GO"]
    assert len(deal["key_differentiators"]) > 0
    assert len(deal["risk_radar"]) > 0


def test_dfir_subagent_panel():
    engine = PresalesAgentEngine()
    rfp = "Need BAS simulation, Compromise Assessment, and Incident Forensics."

    panel = engine.run_dfir_subagent_panel(rfp)
    assert "ca_subagent" in panel
    assert "bas_subagent" in panel
    assert "ifi_subagent" in panel
    assert "retainer_subagent" in panel

    assert panel["ca_subagent"].estimated_hours > 0
    assert "ATT&CK" in panel["bas_subagent"].recommended_scope or "Atomic" in panel["bas_subagent"].recommended_scope


def test_generate_full_proposal_payload():
    engine = PresalesAgentEngine()
    rfp = "CyberDyne Systems ISO 27001 audit and VAPT pentesting."

    payload = engine.generate_full_proposal_payload(rfp)
    assert "opportunity_name" in payload
    assert "executive_summary" in payload
    assert "service_lines" in payload
    assert len(payload["service_lines"]) >= 4
