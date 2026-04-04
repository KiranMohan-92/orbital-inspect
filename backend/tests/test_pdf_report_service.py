import os

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from services.pdf_report_service import generate_html_report


def test_cover_page_css_guards_against_pdf_first_page_overlap():
    html = generate_html_report(
        {
            "classification": {
                "satellite_type": "communications satellite",
                "orbital_regime": "GEO",
                "operator": "Operator With A Very Long Name For Layout Stress Testing",
                "bus_platform": "A Deliberately Long Bus Platform Name To Exercise Cover Wrapping",
            },
            "insurance_risk": {
                "risk_tier": "MEDIUM-HIGH",
                "underwriting_recommendation": "INSURABLE_WITH_EXCLUSIONS",
            },
            "report_completeness": "COMPLETE",
        },
        report_id="OI-LAYOUT-TEST",
    )

    assert "min-height: 252mm;" in html
    assert "width: 100%;" in html
    assert "overflow-wrap: break-word;" in html
    assert "word-break: normal;" in html
    assert "display: table;" in html
    assert "margin: 0 auto 36px;" in html
