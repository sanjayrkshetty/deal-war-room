"""
Big 4 Executive HTML Report Generator (`engine/html_reporter.py`)

Produces Deloitte / McKinsey / PwC consulting-grade Executive Deal Dossiers
with interactive KPI stat cards, risk radar badges, service line breakdowns,
and strategic go/no-go recommendations.
"""

from __future__ import annotations

from typing import TypedDict, Any


class DealAnalysis(TypedDict):
    opportunity_name: str
    client_industry: str
    win_probability: int  # 0 to 100
    deal_recommendation: str  # RECOMMENDED / CONDITIONAL / NO_GO
    risk_level: str  # LOW / MEDIUM / HIGH / CRITICAL
    estimated_hours: int
    key_differentiators: list[str]
    service_line_breakdown: dict[str, str]
    risk_radar: list[str]
    scrubbed_summary: str


def generate_big4_executive_html(deal: DealAnalysis) -> str:
    """
    Generates a responsive Big 4 Executive HTML Deal Intelligence Report.
    """
    win_score = max(0, min(100, deal.get("win_probability", 75)))
    rec = deal.get("deal_recommendation", "RECOMMENDED").upper()
    risk = deal.get("risk_level", "LOW").upper()

    rec_color = "#10B981" if "RECOMMEND" in rec else ("#F59E0B" if "CONDITIONAL" in rec else "#EF4444")
    risk_color = "#10B981" if risk == "LOW" else ("#F59E0B" if risk == "MEDIUM" else "#EF4444")

    differentiators_html = "".join(f"<li>{diff}</li>" for diff in deal.get("key_differentiators", []))
    risk_radar_html = "".join(f"<li class='risk-item'>⚠️ {r}</li>" for r in deal.get("risk_radar", []))

    service_lines_html = ""
    for sl_name, sl_desc in deal.get("service_line_breakdown", {}).items():
        service_lines_html += f"""
        <div class="service-card">
            <h4>{sl_name.upper()}</h4>
            <p>{sl_desc}</p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Deal Intelligence Dossier - {deal.get('opportunity_name', 'Deal Review')}</title>
    <style>
        :root {{
            --bg-primary: #0F172A;
            --bg-card: #1E293B;
            --accent-teal: #0EA5E9;
            --accent-cyan: #06B6D4;
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
            --border-color: #334155;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .brand {{
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: var(--accent-cyan);
        }}
        .subtitle {{
            font-size: 14px;
            color: var(--text-muted);
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }}
        .kpi-value {{
            font-size: 32px;
            font-weight: 800;
            margin: 8px 0;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-weight: 700;
            font-size: 14px;
            color: #FFFFFF;
        }}
        .section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 700;
            color: var(--accent-teal);
            margin-top: 0;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
        }}
        .service-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }}
        .service-card {{
            background: #0F172A;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 16px;
        }}
        .service-card h4 {{
            margin-top: 0;
            color: var(--accent-cyan);
        }}
        ul {{
            padding-left: 20px;
            margin: 0;
        }}
        li {{
            margin-bottom: 8px;
        }}
        .risk-item {{
            color: #F87171;
            font-weight: 500;
        }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 40px;
            border-top: 1px solid var(--border-color);
            padding-top: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="brand">PRESALES INTELLIGENCE</div>
                <div class="subtitle">Big 4 Executive Strategic Deal Dossier</div>
            </div>
            <div style="text-align: right;">
                <span class="badge" style="background-color: {rec_color};">{rec}</span>
            </div>
        </div>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="subtitle">WIN PROBABILITY</div>
                <div class="kpi-value" style="color: var(--accent-cyan);">{win_score}%</div>
                <div class="subtitle">AI Grounded Assessment</div>
            </div>
            <div class="kpi-card">
                <div class="subtitle">DEAL RISK LEVEL</div>
                <div class="kpi-value" style="color: {risk_color};">{risk}</div>
                <div class="subtitle">Scope & SLA Radar</div>
            </div>
            <div class="kpi-card">
                <div class="subtitle">ESTIMATED EFFORT</div>
                <div class="kpi-value" style="color: var(--text-main);">{deal.get('estimated_hours', 120)} hrs</div>
                <div class="subtitle">Total Delivery Scope</div>
            </div>
        </div>

        <div class="section">
            <h3 class="section-title">EXECUTIVE DEEP DIVE & SUMMARY</h3>
            <p>{deal.get('scrubbed_summary', 'Strategic analysis completed using anonymized deal memory.')}</p>
        </div>

        <div class="section">
            <h3 class="section-title">SERVICE LINE SCOPE BREAKDOWN</h3>
            <div class="service-grid">
                {service_lines_html}
            </div>
        </div>

        <div class="section">
            <h3 class="section-title">WIN STRATEGY & DIFFERENTIATORS</h3>
            <ul>
                {differentiators_html}
            </ul>
        </div>

        <div class="section">
            <h3 class="section-title">SCOPE & SLA RISK RADAR</h3>
            <ul>
                {risk_radar_html}
            </ul>
        </div>

        <div class="footer">
            Generated by Presales Intelligence Console • Confidential Strategic Analysis • DLP Scrubbed ✅
        </div>
    </div>
</body>
</html>
"""
    return html
