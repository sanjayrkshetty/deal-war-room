"""
Presales Intelligence Streamlit Application (`app.py`)

Interactive 3-Tab Pre-Sales Deal Intelligence Console:
- Tab 1: Strategic Deal Intelligence & Big 4 Executive HTML Report
- Tab 2: Virtual BU SME Panel (DFIR, VAPT, GRC, SOC) + Interactive Chat
- Tab 3: Grounded Proposal Generator, DLP Scrubbed View, & .docx Export
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

from engine.scrubber import scrub_text, scrub_with_audit
from engine.rag_store import RAGStore
from engine.agents import PresalesAgentEngine
from engine.html_reporter import generate_big4_executive_html
from engine.docx_exporter import export_proposal_docx

# Streamlit Page Config
st.set_page_config(
    page_title="Presales Hub — Strategic Deal Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for Sleek Dark Theme UI
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    .header-badge {
        background: #1E293B;
        border: 1px solid #334155;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 13px;
        color: #38BDF8;
        display: inline-block;
        margin-right: 8px;
    }
    .sme-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .sme-title {
        color: #38BDF8;
        font-weight: 700;
        font-size: 16px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Engine
@st.cache_resource
def get_engine():
    return PresalesAgentEngine(), RAGStore()

agent_engine, rag_store = get_engine()

# Sidebar Setup
st.sidebar.title("🛡️ Presales Intelligence")
st.sidebar.markdown("---")

sample_folder = Path("corpus/synthetic_samples")
sample_options = {"Custom Input": None}

if sample_folder.exists():
    for f in sample_folder.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sample_options[data.get("opportunity_name", f.name)] = data
        except Exception:
            pass

selected_sample_name = st.sidebar.selectbox("Select Sample RFP / Opportunity", list(sample_options.keys()))
selected_sample = sample_options[selected_sample_name]

if selected_sample:
    default_rfp_text = selected_sample.get("rfp_text", "")
else:
    default_rfp_text = (
        "Acme Corporation requires a 24/7 DFIR Emergency Retainer with 2-hour SLA, "
        "annual Compromise Assessment (CA) across 300 endpoints, and OWASP VAPT pentesting."
    )

input_rfp = st.sidebar.text_area("RFP Requirement Payload", value=default_rfp_text, height=220)

run_button = st.sidebar.button("⚡ Run Presales Intelligence Engine", type="primary", use_container_width=True)

# Main Dashboard Header
st.title("🛡️ Presales Hub — Deal Intelligence & Virtual SME Console")
st.markdown(
    """
    <div>
        <span class="header-badge">DLP Scrubber: ACTIVE ✅</span>
        <span class="header-badge">Local Scrubbed DB: READY ✅</span>
        <span class="header-badge">Antigravity SDK Engine: ACTIVE ✅</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# Session State Cache for Execution Output
if "last_payload" not in st.session_state or run_button:
    with st.spinner("Executing Google Antigravity SDK Agents over scrubbed memory bank..."):
        payload = agent_engine.generate_full_proposal_payload(input_rfp)
        st.session_state["last_payload"] = payload
else:
    payload = st.session_state["last_payload"]

deal = payload["deal_analysis"]
dfir_panel = payload["dfir_panel"]
vapt_panel = payload["vapt_panel"]
grc_panel = payload["grc_panel"]

# 3-Tab Interface
tab1, tab2, tab3 = st.tabs([
    "📊 Tab 1: Strategic Deal Strategy & Big 4 HTML Dossier",
    "🤖 Tab 2: Virtual BU SME Panel & Interactive Chat",
    "📄 Tab 3: Grounded Proposal Generator & .docx Export",
])

# =====================================================================
# TAB 1: Strategic Deal Intelligence & Big 4 Executive HTML Report
# =====================================================================
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Win Probability", f"{deal['win_probability']}%", delta="AI Score")
    with col2:
        st.metric("Deal Risk Level", deal['risk_level'], delta="SLA Radar")
    with col3:
        st.metric("Estimated Hours", f"{deal['estimated_hours']} hrs", delta="Delivery Scope")
    with col4:
        st.metric("Recommendation", deal['deal_recommendation'])

    st.markdown("### 🏛️ Big 4 Executive Deal Dossier (Interactive HTML Report)")

    # Render HTML Dossier
    big4_html = generate_big4_executive_html(deal)
    components.html(big4_html, height=650, scrolling=True)

    st.download_button(
        label="📥 Download Big 4 Executive HTML Report (.html)",
        data=big4_html,
        file_name="Big4_Executive_Deal_Intelligence_Report.html",
        mime="text/html",
        use_container_width=True,
    )

# =====================================================================
# TAB 2: Virtual BU SME Panel & Interactive Chat
# =====================================================================
with tab2:
    st.markdown("### 🤖 Virtual BU SME Review Panel")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(
            f"""
            <div class="sme-card">
                <div class="sme-title">🔍 DFIR SME Subagent (CA / BAS / IFI / Retainer)</div>
                <p><b>Compromise Assessment Scope:</b> {dfir_panel['ca_subagent'].recommended_scope}</p>
                <p><b>BAS Attack Sim:</b> {dfir_panel['bas_subagent'].recommended_scope}</p>
                <p><b>Retainer SLA:</b> {dfir_panel['retainer_subagent'].recommended_scope}</p>
                <small style="color: #94A3B8;">Grounded in: {dfir_panel['ca_subagent'].grounding_source}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="sme-card">
                <div class="sme-title">📋 GRC & Compliance SME Subagent</div>
                <p><b>Scope:</b> {grc_panel.recommended_scope}</p>
                <p><b>Framework Alignment:</b> {', '.join(grc_panel.compliance_mappings)}</p>
                <small style="color: #94A3B8;">Grounded in: {grc_panel.grounding_source}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_b:
        st.markdown(
            f"""
            <div class="sme-card">
                <div class="sme-title">🛡️ VAPT / OffSec SME Subagent</div>
                <p><b>Scope:</b> {vapt_panel.recommended_scope}</p>
                <p><b>Framework Alignment:</b> {', '.join(vapt_panel.compliance_mappings)}</p>
                <small style="color: #94A3B8;">Grounded in: {vapt_panel.grounding_source}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="sme-card">
                <div class="sme-title">☁️ Managed SOC & SIEM Sizing Subagent</div>
                <p><b>Scope:</b> Log ingestion EPS/GB sizing, EDR deployment scale, 24/7 L1/L2 escalation workflows.</p>
                <small style="color: #94A3B8;">Grounded in: 24/7 Managed SOC & SIEM Sizing Template</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 💬 Interactive Virtual BU SME Chat")

    chat_input = st.text_input("Ask a Virtual SME (e.g., @DFIR How do we scope Compromise Assessment for 500 endpoints?)")
    if chat_input:
        with st.chat_message("user"):
            st.write(chat_input)

        with st.chat_message("assistant"):
            scrubbed_query = scrub_text(chat_input)
            retrieved = rag_store.search_memory(scrubbed_query, top_k=2)

            ans = (
                f"**Virtual SME Response (Grounded in {retrieved[0]['title']})**:\n\n"
                f"For the requested scope, we recommend a 2-stage execution:\n"
                f"1. **Stage 1 (Deployment & Sweep)**: Deploy lightweight collection agent across domain endpoints to sweep for IOCs and active C2 beacons.\n"
                f"2. **Stage 2 (Forensics & Report)**: Perform memory artifact extraction and deliver an Executive Compromise Dossier within 5 business days.\n\n"
                f"*DLP Note: Input query was sanitized locally before processing.*"
            )
            st.markdown(ans)

# =====================================================================
# TAB 3: Grounded Proposal Generator & .docx Export
# =====================================================================
with tab3:
    st.markdown("### 📄 Generated Proposal Content")

    show_scrubbed = st.checkbox("🔍 Show Scrubbed Payload Transparency View (DLP Proof)")

    if show_scrubbed:
        audit = scrub_with_audit(input_rfp)
        st.info(f"DLP Sanitization Audit: Redacted {audit['redactions_count']} categories: {', '.join(audit['categories_redacted'])}")
        st.code(audit['scrubbed_text'], language="markdown")
        st.markdown("---")

    st.markdown(f"#### Proposal Title: {payload['opportunity_name']}")
    st.markdown(f"**Executive Summary:** {payload['executive_summary']}")

    st.markdown("#### Technical Service Line Scope")
    for s_name, s_desc in payload["service_lines"].items():
        st.markdown(f"- **{s_name}**: {s_desc}")

    st.markdown("#### Delivery Methodology")
    st.write(payload["methodology"])

    st.markdown("---")

    # Export .docx Button
    output_docx_path = Path("corpus/generated_proposal.docx")
    export_proposal_docx(payload, output_docx_path)

    with open(output_docx_path, "rb") as fp:
        st.download_button(
            label="📥 Download Grounded Proposal Document (.docx)",
            data=fp,
            file_name="Presales_Intelligence_Grounded_Proposal.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            type="primary",
        )
