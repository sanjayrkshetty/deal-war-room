# 🛡️ Presales Intelligence (`presales-intelligence`)

An AI-native pre-sales and deal intelligence platform powered by the **Google Antigravity SDK**, local MiniLM vector RAG memory, local DLP sanitization, virtual BU SME bots, and Big 4 consulting-grade executive HTML deal reports.

---

## 🚀 Key Features

1. **Google Antigravity SDK Multi-Agent Engine**:
   - `StrategicDealConsultantAgent`: Win probability score (0–100%), scope risk radar, SLA penalty warnings, and pitch differentiators.
   - `DFIRSubagentPanel`: Specialized subagents for Compromise Assessment (CA), Breach & Attack Simulation (BAS), Incident Forensics & Investigation (IFI), and DFIR Retainer SLA tiering.
   - `VAPTSubagentPanel`: Web & API pentesting, OWASP Top 10, network/cloud infra reviews, and Red Teaming.
   - `GRCSubagentPanel`: ISO 27001:2022, PCI-DSS 4.0, SOC 2 Type II audit readiness, and vendor risk governance.
   - `ManagedSOCPanel`: SIEM log ingestion sizing (EPS/GB per day), EDR deployment scale, and 24/7 detection runbooks.

2. **Zero-Trust Local DLP Sanitization**:
   - Compulsory local scrubber (`engine/scrubber.py`) redacts 100% of employer references, client names, employee names, IPs, emails, credentials, and financial figures *before* vector indexing or LLM inference.
   - All text processed with safe placeholders (`[CLIENT_NAME]`, `[SME_NAME]`, `[SCRUBBED_SCOPE]`).

3. **Grounded Memory Bank & Fallback**:
   - Local vector store (`presales_intelligence.db`) with MiniLM local embeddings.
   - **Grounding Fallback**: If memory search relevance is low, automatically falls back to built-in cybersecurity frameworks (SANS DFIR, OWASP, ISO 27001, NIST).

4. **Big 4 Executive HTML Dossier**:
   - Renders a Deloitte / McKinsey / PwC style responsive HTML Deal Report live in Tab 1, exportable as a standalone `.html` report.

5. **Streamlit 3-Tab Web Console & Free Cloud Deployment**:
   - Interactive UI with live status indicators, synthetic RFP selectors (*Acme Corp VAPT*, *Globex DFIR Retainer*, *CyberDyne GRC*), "Show Scrubbed Payload" DLP view, and 1-click `.docx` proposal export.

---

## 🛠️ Quickstart Guide

### 1. Installation
```bash
cd C:\Users\SISASanjayShetty\Documents\presales-intelligence
pip install -r requirements.txt
```

### 2. One-Time Offline Database Ingestion
```bash
python scrub_and_ingest.py
```

### 3. Launch Streamlit Application
```bash
streamlit run app.py
```

### 4. Run Unit Tests
```bash
pytest
```

---

## 🔒 Security & Data Compliance
- **Zero Live OneDrive Access**: The application runtime NEVER accesses OneDrive or holds file handles to employer folders.
- **Git Protection**: `corpus/raw` and `.env` are listed in `.gitignore`. No raw proposal data or credentials committed to Git.
