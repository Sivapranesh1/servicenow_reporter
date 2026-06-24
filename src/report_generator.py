"""Generate HTML and Excel reports."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Template

from src.incident_analyzer import AnalysisResult

logger = logging.getLogger("servicenow_reporter")

# Inline Jinja2 template (kept self-contained; can be moved to a file).
HTML_TEMPLATE = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{ subject }}</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;color:#222;margin:0;padding:18px;}
 h1{font-size:20px;color:#0b5394;margin-bottom:4px;}
 h2{font-size:15px;color:#0b5394;border-bottom:2px solid #0b5394;padding-bottom:4px;margin-top:24px;}
 .meta{color:#555;font-size:12px;margin-bottom:18px;}
 .summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;}
 .card{background:#f4f8fc;border-left:4px solid #0b5394;padding:10px 14px;border-radius:4px;}
 .card .num{font-size:22px;font-weight:bold;color:#0b5394;}
 .card .lbl{font-size:12px;color:#555;}
 table{border-collapse:collapse;width:100%;font-size:12px;}
 th{background:#0b5394;color:#fff;padding:6px;text-align:left;}
 td{border:1px solid #ddd;padding:5px;vertical-align:top;}
 tr:nth-child(even){background:#fafafa;}
 .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold;}
 .pill-red{background:#fde2e2;color:#a30000;}
 .pill-amber{background:#fff4d6;color:#8a6100;}
 .pill-green{background:#e1f5e1;color:#1b6b1b;}
 .footer{margin-top:30px;font-size:11px;color:#888;}
</style></head><body>

<h1>📊 Daily ServiceNow Incident Status Report</h1>
<div class="meta">Generated: {{ summary.report_date }}</div>

<h2>Executive Summary</h2>
<div class="summary-grid">
  <div class="card"><div class="num">{{ summary.total_incidents }}</div><div class="lbl">Total Incidents</div></div>
  <div class="card"><div class="num">{{ summary.total_on_hold }}</div><div class="lbl">On Hold</div></div>
  {% for h in stale_hours %}
  <div class="card"><div class="num">{{ summary['not_updated_' ~ h ~ 'h'] }}</div>
       <div class="lbl">Not updated in {{ h }}h</div></div>
  {% endfor %}
</div>

<h2>Aging Distribution</h2>
<table><tr><th>Bucket</th><th>Count</th></tr>
{% for b, c in aging.items() %}<tr><td>{{ b }}</td><td>{{ c }}</td></tr>{% endfor %}
</table>

<h2>Detailed Incident Table</h2>
{{ detail_table | safe }}

<h2>⚠ Exceptions</h2>
{% for name, df_html in exception_tables.items() %}
  <h3 style="color:#a30000;">{{ name }}</h3>
  {{ df_html | safe }}
{% endfor %}

<div class="footer">Automated report. Do not reply. — ServiceNow Reporter Bot</div>
</body></html>
"""

DETAIL_COLUMNS = [
    "incident_number", "state", "last_updated", "hours_since_update",
    "dependency", "hold_reason", "assignment_group", "assigned_to",
]

PRETTY = {
    "incident_number": "Incident #",
    "state": "State",
    "last_updated": "Last Updated",
    "hours_since_update": "Hrs Since Update",
    "dependency": "Dependency",
    "hold_reason": "Hold Reason",
    "assignment_group": "Assignment Group",
    "assigned_to": "Assigned To",
    "short_description": "Short Description",
    "priority": "Priority",
    "business_service": "Business Service",
    "opened_date": "Opened",
    "aging_bucket": "Aging",
}


def _df_to_html(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "<p><i>No records.</i></p>"
    sub = df[[c for c in columns if c in df.columns]].copy()
    sub.rename(columns=PRETTY, inplace=True)
    return sub.to_html(index=False, escape=True, border=0)


def build_html_report(result: AnalysisResult, stale_hours: list[int], subject: str) -> str:
    detail_html = _df_to_html(result.enriched, DETAIL_COLUMNS)

    exception_tables = {
        name.replace("_", " ").title(): _df_to_html(df, DETAIL_COLUMNS)
        for name, df in result.exceptions.items()
    }

    template = Template(HTML_TEMPLATE)
    return template.render(
        subject=subject,
        summary=result.summary,
        aging=result.aging_distribution,
        detail_table=detail_html,
        exception_tables=exception_tables,
        stale_hours=stale_hours,
    )


def write_html(html: str, out_folder: str | Path) -> Path:
    out = Path(out_folder)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"incident_report_{datetime.now():%Y%m%d_%H%M%S}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("HTML report written: %s", path)
    return path


def write_excel(result: AnalysisResult, out_folder: str | Path) -> Path:
    out = Path(out_folder)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"incident_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        # Summary
        pd.DataFrame(list(result.summary.items()), columns=["Metric", "Value"]).to_excel(
            writer, sheet_name="Summary", index=False
        )
        # Aging
        pd.DataFrame(
            list(result.aging_distribution.items()), columns=["Aging Bucket", "Count"]
        ).to_excel(writer, sheet_name="Aging", index=False)
        # Detail
        result.enriched.to_excel(writer, sheet_name="Incidents", index=False)
        # Exceptions
        for name, df in result.exceptions.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)

        # Light formatting
        wb = writer.book
        hdr_fmt = wb.add_format(
            {"bold": True, "bg_color": "#0b5394", "font_color": "white", "border": 1}
        )
        for ws_name in writer.sheets:
            ws = writer.sheets[ws_name]
            ws.set_row(0, None, hdr_fmt)
            ws.autofilter(0, 0, 0, 5)
            ws.freeze_panes(1, 0)

    logger.info("Excel report written: %s", path)
    return path
