"""
Satellite Condition Report generator.

Generates HTML reports from analysis data using Jinja2 templates.
HTML can be served directly or converted to PDF via WeasyPrint (when available).

The report is the product deliverable — what insurers pay $50K-500K for.
"""

import logging
from pathlib import Path
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

log = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def _format_usd(value) -> str:
    """Format USD values: $1.2B, $500M, $12K."""
    if value is None:
        return "N/A"
    v = float(value)
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.0f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def _format_pct(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.1f}%"


def _severity_color(severity: str) -> str:
    colors = {
        "CRITICAL": "#ef4444",
        "SEVERE": "#f97316",
        "MODERATE": "#eab308",
        "MINOR": "#84cc16",
        "LOW": "#22c55e",
        "MEDIUM": "#eab308",
        "MEDIUM-HIGH": "#f97316",
        "HIGH": "#ef4444",
    }
    return colors.get(severity, "#8890a8")


def _uw_color(rec: str) -> str:
    colors = {
        "INSURABLE_STANDARD": "#22c55e",
        "INSURABLE_ELEVATED_PREMIUM": "#eab308",
        "INSURABLE_WITH_EXCLUSIONS": "#f97316",
        "FURTHER_INVESTIGATION": "#8b5cf6",
        "UNINSURABLE": "#ef4444",
    }
    return colors.get(rec, "#8890a8")


# Register filters
_jinja_env.filters["format_usd"] = _format_usd
_jinja_env.filters["format_pct"] = _format_pct
_jinja_env.filters["severity_color"] = _severity_color
_jinja_env.filters["uw_color"] = _uw_color


def generate_html_report(
    analysis_data: dict,
    report_id: str = "",
) -> str:
    """
    Generate an HTML Satellite Condition Report.

    Args:
        analysis_data: Dict containing classification, vision, environment,
                      failure_mode, and insurance_risk results
        report_id: Report identifier for the header

    Returns:
        HTML string of the complete report
    """
    template = _jinja_env.get_template("report.html")

    context = {
        "report_id": report_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "classification": analysis_data.get("classification", {}),
        "vision": analysis_data.get("vision", {}),
        "environment": analysis_data.get("environment", {}),
        "failure_mode": analysis_data.get("failure_mode", {}),
        "insurance_risk": analysis_data.get("insurance_risk", {}),
        "evidence_gaps": analysis_data.get("evidence_gaps", []),
        "report_completeness": analysis_data.get("report_completeness", "COMPLETE"),
    }

    return template.render(**context)


def generate_pdf_report(analysis_data: dict, report_id: str = "") -> bytes | None:
    """
    Generate a PDF Satellite Condition Report.

    Requires WeasyPrint to be installed. Returns None if unavailable.
    """
    html = generate_html_report(analysis_data, report_id)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        log.info("PDF report generated", report_id=report_id, size_bytes=len(pdf_bytes))
        return pdf_bytes
    except ImportError:
        log.warning("WeasyPrint not available — returning HTML only")
        return None
