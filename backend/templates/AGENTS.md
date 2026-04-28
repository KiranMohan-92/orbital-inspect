<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# templates

## Purpose
Jinja HTML templates for server-side rendering. Currently the single PDF report template consumed by `../services/pdf_report_service.py` (Audit Rec #12).

## Key Files
| File | Description |
|------|-------------|
| `report.html` | Analysis report layout — renders evidence, risk matrix, provenance, recommendation |

## For AI Agents

### Working In This Directory
- Rendered by `../services/pdf_report_service.py` — changes here should be validated against `../tests/test_pdf_report_service.py`.
- Keep styles inline or embedded; PDF renderer (weasyprint/reportlab) may not fetch external CSS.
- Never inject untrusted HTML — escape all user-provided strings.

### Testing Requirements
- `../tests/test_pdf_report_service.py` renders the template against fixtures.

## Dependencies

### Internal
- Consumed only by `../services/pdf_report_service.py`.

### External
- Jinja2.

<!-- MANUAL: -->
