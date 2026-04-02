"""
Report management API — review and approval workflow.

Report lifecycle: DRAFT → PENDING_REVIEW → APPROVED → PUBLISHED
                                         → REJECTED (with comments)
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from auth.dependencies import get_current_user, require_role, CurrentUser

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])
_REPORTABLE_ANALYSIS_STATUSES = {"completed", "completed_partial"}


class SubmitReviewRequest(BaseModel):
    notes: str = ""


class ApproveRequest(BaseModel):
    comments: str = ""


class RejectRequest(BaseModel):
    reason: str


@router.post("/{analysis_id}/create")
async def create_report(
    analysis_id: str,
    user: CurrentUser | None = Depends(require_role("analyst")),
):
    """Create a draft report from a completed analysis."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository, ReportRepository

        async with async_session_factory() as session:
            analysis_repo = AnalysisRepository(session)
            analysis = await analysis_repo.get(analysis_id, org_id=user.org_id if user else None)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            if analysis.status not in _REPORTABLE_ANALYSIS_STATUSES:
                raise HTTPException(status_code=400, detail="Analysis not yet completed")

            report_repo = ReportRepository(session)
            existing = await report_repo.get_by_analysis(analysis_id, org_id=user.org_id if user else None)
            if existing:
                return {"id": existing.id, "status": existing.status, "message": "Report already exists"}

            full_report = {
                "classification": analysis.classification_result,
                "vision": analysis.vision_result,
                "environment": analysis.environment_result,
                "failure_mode": analysis.failure_mode_result,
                "insurance_risk": analysis.insurance_risk_result,
                "evidence_gaps": analysis.evidence_gaps,
                "report_completeness": analysis.report_completeness,
            }
            report = await report_repo.create(analysis_id, full_report)
            return {"id": report.id, "status": report.status}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.post("/{report_id}/submit-review")
async def submit_for_review(
    report_id: str,
    body: SubmitReviewRequest,
    user: CurrentUser | None = Depends(require_role("analyst")),
):
    """Submit a draft report for review."""
    try:
        from db.base import async_session_factory
        from db.repository import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            report = await repo.get(report_id, org_id=user.org_id if user else None)
            if not report:
                raise HTTPException(status_code=404, detail="Report not found")
            if report.status != "DRAFT":
                raise HTTPException(status_code=400, detail=f"Cannot submit: report is {report.status}")

            await repo.update_status(
                report_id,
                "PENDING_REVIEW",
                submitted_by=user.user_id if user else "anonymous",
                submitted_at=datetime.now(timezone.utc),
            )
            log.info("Report submitted for review", extra={"report_id": report_id})
            return {"id": report_id, "status": "PENDING_REVIEW"}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.post("/{report_id}/approve")
async def approve_report(
    report_id: str,
    body: ApproveRequest,
    user: CurrentUser | None = Depends(require_role("admin")),
):
    """Approve a report (admin only)."""
    try:
        from db.base import async_session_factory
        from db.repository import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            report = await repo.get(report_id, org_id=user.org_id if user else None)
            if not report:
                raise HTTPException(status_code=404, detail="Report not found")
            if report.status != "PENDING_REVIEW":
                raise HTTPException(status_code=400, detail=f"Cannot approve: report is {report.status}")

            comments = list(report.reviewer_comments or [])
            if body.comments:
                comments.append({
                    "reviewer": user.user_id if user else "anonymous",
                    "comment": body.comments,
                    "action": "APPROVED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            await repo.update_status(
                report_id,
                "APPROVED",
                approved_by=user.user_id if user else "anonymous",
                approved_at=datetime.now(timezone.utc),
                reviewer_comments=comments,
            )
            log.info("Report approved", extra={"report_id": report_id})
            return {"id": report_id, "status": "APPROVED"}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.post("/{report_id}/reject")
async def reject_report(
    report_id: str,
    body: RejectRequest,
    user: CurrentUser | None = Depends(require_role("admin")),
):
    """Reject a report with reason (admin only)."""
    try:
        from db.base import async_session_factory
        from db.repository import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            report = await repo.get(report_id, org_id=user.org_id if user else None)
            if not report:
                raise HTTPException(status_code=404, detail="Report not found")
            if report.status != "PENDING_REVIEW":
                raise HTTPException(status_code=400, detail=f"Cannot reject: report is {report.status}")

            comments = list(report.reviewer_comments or [])
            comments.append({
                "reviewer": user.user_id if user else "anonymous",
                "comment": body.reason,
                "action": "REJECTED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            await repo.update_status(
                report_id,
                "DRAFT",  # Reset to DRAFT so analyst can revise
                reviewer_comments=comments,
            )
            log.info("Report rejected", extra={"report_id": report_id})
            return {"id": report_id, "status": "DRAFT", "reason": body.reason}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Get report details including review history."""
    try:
        from db.base import async_session_factory
        from db.repository import ReportRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            report = await repo.get(report_id, org_id=user.org_id if user else None)
            if not report:
                raise HTTPException(status_code=404, detail="Report not found")

            return {
                "id": report.id,
                "analysis_id": report.analysis_id,
                "status": report.status,
                "version": report.version,
                "full_report": report.full_report_json,
                "submitted_by": report.submitted_by,
                "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
                "approved_by": report.approved_by,
                "approved_at": report.approved_at.isoformat() if report.approved_at else None,
                "reviewer_comments": report.reviewer_comments,
                "created_at": report.created_at.isoformat() if report.created_at else None,
            }
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.post("/inline/generate-pdf")
async def generate_inline_pdf(
    data: dict,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Generate a NASA-grade report from inline analysis data (no DB required)."""
    try:
        from services.pdf_report_service import generate_html_report
        from starlette.responses import HTMLResponse

        html = generate_html_report(data)
        return HTMLResponse(content=html, media_type="text/html")
    except Exception as e:
        log.error("Inline PDF generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Report generation failed")


@router.post("/{analysis_id}/generate-pdf")
async def generate_pdf(
    analysis_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
    """Generate a NASA-grade HTML Satellite Condition Report from DB."""
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository
        from services.pdf_report_service import generate_html_report

        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            analysis = await repo.get(analysis_id, org_id=user.org_id if user else None)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            if analysis.status not in _REPORTABLE_ANALYSIS_STATUSES:
                raise HTTPException(status_code=400, detail="Analysis not yet completed")

            report_data = {
                "classification": analysis.classification_result or {},
                "vision": analysis.vision_result or {},
                "environment": analysis.environment_result or {},
                "failure_mode": analysis.failure_mode_result or {},
                "insurance_risk": analysis.insurance_risk_result or {},
                "evidence_gaps": analysis.evidence_gaps or [],
                "report_completeness": analysis.report_completeness or "COMPLETE",
            }

            html = generate_html_report(report_data, report_id=analysis_id[:12])

            from starlette.responses import HTMLResponse
            return HTMLResponse(content=html, media_type="text/html")
    except ImportError:
        raise HTTPException(status_code=503, detail="PDF service not available")
