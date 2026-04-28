"""
NASA-grade Satellite Condition Report generator.

Produces a multi-page HTML report matching NASA Technical Report format.
Charts are rendered server-side via matplotlib, damage overlays via Pillow.
All images embedded as base64 data URIs for self-contained output.
"""

import base64
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


def _b64_png(png_bytes: bytes) -> str:
    """Convert PNG bytes to a data URI for HTML embedding."""
    return f"data:image/png;base64,{base64.b64encode(png_bytes).decode()}"


def _format_usd(value) -> str:
    if value is None:
        return "N/A"
    v = float(value)
    if v >= 1_000_000_000:
        return f"${v/1e9:.1f}B"
    if v >= 1_000_000:
        return f"${v/1e6:.0f}M"
    if v >= 1_000:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def _format_pct(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.1f}%"


def _severity_color(severity: str) -> str:
    return {
        "CRITICAL": "#ef4444",
        "SEVERE": "#f97316",
        "HIGH": "#ef4444",
        "MODERATE": "#eab308",
        "MEDIUM": "#eab308",
        "MEDIUM-HIGH": "#f97316",
        "MINOR": "#84cc16",
        "LOW": "#22c55e",
    }.get(severity, "#8890a8")


def _uw_color(rec: str) -> str:
    return {
        "INSURABLE_STANDARD": "#22c55e",
        "INSURABLE_ELEVATED_PREMIUM": "#eab308",
        "INSURABLE_WITH_EXCLUSIONS": "#f97316",
        "FURTHER_INVESTIGATION": "#8b5cf6",
        "UNINSURABLE": "#ef4444",
    }.get(rec, "#8890a8")


# Register Jinja2 filters
_jinja_env.filters["format_usd"] = _format_usd
_jinja_env.filters["format_pct"] = _format_pct
_jinja_env.filters["severity_color"] = _severity_color
_jinja_env.filters["uw_color"] = _uw_color


def generate_html_report(
    analysis_data: dict,
    report_id: str = "",
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
) -> str:
    """Generate a NASA-grade HTML Satellite Condition Report."""
    template = _jinja_env.get_template("report.html")

    # Extract sub-dicts
    insurance = analysis_data.get("insurance_risk", {})
    classification = analysis_data.get("classification", {})
    vision = analysis_data.get("vision", {})
    failure_mode = analysis_data.get("failure_mode", {})

    # Generate charts; failures are logged but never fatal
    chart_images: dict[str, str] = {}

    # Risk matrix chart
    rm = insurance.get("risk_matrix", {})
    if rm:
        try:
            from services.chart_renderer import render_risk_matrix_chart
            chart_images["risk_matrix"] = _b64_png(render_risk_matrix_chart(
                rm.get("severity", {}).get("score", 0),
                rm.get("probability", {}).get("score", 0),
                rm.get("consequence", {}).get("score", 0),
                rm.get("composite", 0),
                rm.get("severity", {}).get("reasoning", ""),
                rm.get("probability", {}).get("reasoning", ""),
                rm.get("consequence", {}).get("reasoning", ""),
            ))
        except Exception as e:
            log.warning("Risk matrix chart failed: %s", e)

    # Composite gauge
    if rm.get("composite"):
        try:
            from services.chart_renderer import render_composite_gauge
            chart_images["composite_gauge"] = _b64_png(
                render_composite_gauge(rm["composite"])
            )
        except Exception as e:
            log.warning("Composite gauge failed: %s", e)

    # Degradation timeline
    try:
        from services.chart_renderer import render_degradation_timeline
        chart_images["degradation"] = _b64_png(render_degradation_timeline(
            classification.get("design_life_years"),
            classification.get("estimated_age_years"),
            insurance.get("estimated_remaining_life_years"),
            insurance.get("power_margin_percentage"),
            insurance.get("annual_degradation_rate_pct"),
        ))
    except Exception as e:
        log.warning("Degradation chart failed: %s", e)

    # Damage distribution
    damages = vision.get("damages", [])
    if damages:
        try:
            from services.chart_renderer import render_damage_distribution
            chart_images["damage_dist"] = _b64_png(render_damage_distribution(damages))
        except Exception as e:
            log.warning("Damage distribution chart failed: %s", e)

    # Sensitivity tornado chart
    sa = insurance.get("sensitivity_analysis", {})
    if sa and sa.get("parameters"):
        try:
            from services.chart_renderer import render_sensitivity_tornado
            chart_images["sensitivity_tornado"] = _b64_png(render_sensitivity_tornado(
                sa.get("parameters", []),
                baseline_recommendation=sa.get("baseline_recommendation", ""),
                robustness=sa.get("recommendation_robustness", "MODERATE"),
            ))
        except Exception as e:
            log.warning("Sensitivity tornado chart failed: %s", e)

    # Annotated satellite image
    if image_bytes and damages:
        try:
            from services.image_annotator import annotate_satellite_image
            annotated = annotate_satellite_image(image_bytes, damages, image_mime)
            chart_images["annotated_image"] = _b64_png(annotated)
        except Exception as e:
            log.warning("Image annotation failed: %s", e)
    elif image_bytes:
        chart_images["annotated_image"] = (
            f"data:{image_mime};base64,{base64.b64encode(image_bytes).decode()}"
        )

    context = {
        "report_id": report_id or f"OI-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "generated_year": datetime.now(timezone.utc).year,
        "assessment_mode": analysis_data.get("assessment_mode") or insurance.get("assessment_mode", "PUBLIC_SCREEN"),
        "decision_authority": analysis_data.get("decision_authority") or insurance.get("decision_authority", "SCREENING_ONLY"),
        "report_title": analysis_data.get("report_title") or insurance.get("report_title", "Public Risk Screen"),
        "required_evidence_gaps": analysis_data.get("required_evidence_gaps") or insurance.get("required_evidence_gaps", []),
        "unsupported_claims_blocked": analysis_data.get("unsupported_claims_blocked") or insurance.get("unsupported_claims_blocked", []),
        "classification": classification,
        "vision": vision,
        "environment": analysis_data.get("environment", {}),
        "failure_mode": failure_mode,
        "insurance_risk": insurance,
        "evidence_gaps": analysis_data.get("evidence_gaps", []),
        "report_completeness": analysis_data.get("report_completeness", "COMPLETE"),
        "charts": chart_images,
    }

    return template.render(**context)


def generate_pdf_report(
    analysis_data: dict,
    report_id: str = "",
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
) -> bytes | None:
    """Generate PDF. Returns None if WeasyPrint unavailable."""
    html = generate_html_report(analysis_data, report_id, image_bytes, image_mime)
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        log.info("PDF generated: %d bytes", len(pdf_bytes))
        return pdf_bytes
    except ImportError:
        log.warning("WeasyPrint not available — HTML only")
        return None
