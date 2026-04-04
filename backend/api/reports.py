"""
Report management API — review, approval, and artifact workflow.
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from starlette.responses import HTMLResponse, Response

from auth.dependencies import get_current_user, require_role, require_rate_limit, CurrentUser
from auth.jwt_service import create_artifact_token, decode_token, AuthError
from config import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])
_REPORTABLE_ANALYSIS_STATUSES = {"completed", "completed_partial"}


class SubmitReviewRequest(BaseModel):
    notes: str = ""


class ApproveRequest(BaseModel):
    comments: str = ""


class RejectRequest(BaseModel):
    reason: str


def _report_payload(analysis) -> dict:
    return {
        "classification": analysis.classification_result,
        "vision": analysis.vision_result,
        "environment": analysis.environment_result,
        "failure_mode": analysis.failure_mode_result,
        "insurance_risk": analysis.insurance_risk_result,
        "evidence_gaps": analysis.evidence_gaps,
        "report_completeness": analysis.report_completeness,
    }


def _governance_summary(analysis) -> dict:
    return {
        "policy_version": getattr(analysis, "governance_policy_version", None),
        "model_manifest": getattr(analysis, "model_manifest", {}) or {},
        "human_review_required": getattr(analysis, "human_review_required", True),
        "decision_blocked_reason": getattr(analysis, "decision_blocked_reason", None),
    }


@router.post("/{analysis_id}/create")
async def create_report(
    analysis_id: str,
    user: CurrentUser | None = Depends(require_role("analyst")),
    _rate_limit=Depends(require_rate_limit("report")),
):
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository, ReportRepository, AuditLogRepository

        async with async_session_factory() as session:
            analysis_repo = AnalysisRepository(session)
            report_repo = ReportRepository(session)
            audit_logs = AuditLogRepository(session)

            analysis = await analysis_repo.get(analysis_id, org_id=user.org_id if user else None)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            if analysis.status not in _REPORTABLE_ANALYSIS_STATUSES:
                raise HTTPException(status_code=400, detail="Analysis not yet completed")

            existing = await report_repo.get_by_analysis(analysis_id, org_id=user.org_id if user else None)
            if existing:
                return {"id": existing.id, "status": existing.status, "message": "Report already exists"}

            report = await report_repo.create(
                analysis_id,
                _report_payload(analysis),
                governance_summary=_governance_summary(analysis),
                human_review_required=getattr(analysis, "human_review_required", True),
            )
            await audit_logs.create(
                org_id=user.org_id if user else None,
                actor_id=user.user_id if user else "anonymous",
                action="report.created",
                resource_type="report",
                resource_id=report.id,
                metadata_json={"analysis_id": analysis_id},
                analysis_id=analysis_id,
            )
            return {"id": report.id, "status": report.status}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.post("/{report_id}/submit-review")
async def submit_for_review(
    report_id: str,
    body: SubmitReviewRequest,
    user: CurrentUser | None = Depends(require_role("analyst")),
    _rate_limit=Depends(require_rate_limit("report")),
):
    try:
        from db.base import async_session_factory
        from db.repository import ReportRepository, AuditLogRepository
        from services.webhook_service import dispatch_registered_webhooks

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            audit_logs = AuditLogRepository(session)
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
            await audit_logs.create(
                org_id=user.org_id if user else None,
                actor_id=user.user_id if user else "anonymous",
                action="report.submitted_for_review",
                resource_type="report",
                resource_id=report_id,
                metadata_json={"notes": body.notes},
                analysis_id=report.analysis_id,
            )
            return {"id": report_id, "status": "PENDING_REVIEW"}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.post("/{report_id}/approve")
async def approve_report(
    report_id: str,
    body: ApproveRequest,
    user: CurrentUser | None = Depends(require_role("admin")),
    _rate_limit=Depends(require_rate_limit("report")),
):
    try:
        from db.base import async_session_factory
        from db.repository import ReportRepository, AuditLogRepository
        from services.webhook_service import dispatch_registered_webhooks

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            audit_logs = AuditLogRepository(session)
            report = await repo.get(report_id, org_id=user.org_id if user else None)
            if not report:
                raise HTTPException(status_code=404, detail="Report not found")
            if report.status != "PENDING_REVIEW":
                raise HTTPException(status_code=400, detail=f"Cannot approve: report is {report.status}")

            comments = list(report.reviewer_comments or [])
            if body.comments:
                comments.append(
                    {
                        "reviewer": user.user_id if user else "anonymous",
                        "comment": body.comments,
                        "action": "APPROVED",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

            await repo.update_status(
                report_id,
                "APPROVED",
                approved_by=user.user_id if user else "anonymous",
                approved_at=datetime.now(timezone.utc),
                reviewer_comments=comments,
            )
            await audit_logs.create(
                org_id=user.org_id if user else None,
                actor_id=user.user_id if user else "anonymous",
                action="report.approved",
                resource_type="report",
                resource_id=report_id,
                metadata_json={"comments": body.comments},
                analysis_id=report.analysis_id,
            )
            await dispatch_registered_webhooks(
                org_id=user.org_id if user else None,
                event_type="report.approved",
                payload={"report_id": report_id, "analysis_id": report.analysis_id, "status": "APPROVED"},
            )
            return {"id": report_id, "status": "APPROVED"}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.post("/{report_id}/reject")
async def reject_report(
    report_id: str,
    body: RejectRequest,
    user: CurrentUser | None = Depends(require_role("admin")),
    _rate_limit=Depends(require_rate_limit("report")),
):
    try:
        from db.base import async_session_factory
        from db.repository import ReportRepository, AuditLogRepository

        async with async_session_factory() as session:
            repo = ReportRepository(session)
            audit_logs = AuditLogRepository(session)
            report = await repo.get(report_id, org_id=user.org_id if user else None)
            if not report:
                raise HTTPException(status_code=404, detail="Report not found")
            if report.status != "PENDING_REVIEW":
                raise HTTPException(status_code=400, detail=f"Cannot reject: report is {report.status}")

            comments = list(report.reviewer_comments or [])
            comments.append(
                {
                    "reviewer": user.user_id if user else "anonymous",
                    "comment": body.reason,
                    "action": "REJECTED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            await repo.update_status(
                report_id,
                "DRAFT",
                reviewer_comments=comments,
            )
            await audit_logs.create(
                org_id=user.org_id if user else None,
                actor_id=user.user_id if user else "anonymous",
                action="report.rejected",
                resource_type="report",
                resource_id=report_id,
                metadata_json={"reason": body.reason},
                analysis_id=report.analysis_id,
            )
            return {"id": report_id, "status": "DRAFT", "reason": body.reason}
    except ImportError:
        raise HTTPException(status_code=503, detail="Database not available")


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    user: CurrentUser | None = Depends(get_current_user),
):
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
                "artifact_path": report.artifact_path,
                "artifact_kind": report.artifact_kind,
                "artifact_content_type": report.artifact_content_type,
                "artifact_size_bytes": report.artifact_size_bytes,
                "retention_until": report.retention_until.isoformat() if report.retention_until else None,
                "governance_summary": report.governance_summary,
                "human_review_required": report.human_review_required,
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
    _rate_limit=Depends(require_rate_limit("report")),
):
    try:
        from services.pdf_report_service import generate_html_report

        html = generate_html_report(data)
        return HTMLResponse(content=html, media_type="text/html")
    except Exception as e:
        log.error("Inline PDF generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Report generation failed")


@router.post("/{analysis_id}/generate-pdf")
async def generate_pdf(
    analysis_id: str,
    user: CurrentUser | None = Depends(get_current_user),
    _rate_limit=Depends(require_rate_limit("report")),
):
    try:
        from db.base import async_session_factory
        from db.repository import AnalysisRepository, ReportRepository, AuditLogRepository
        from services.pdf_report_service import generate_html_report, generate_pdf_report
        from services.storage_service import get_storage_backend

        async with async_session_factory() as session:
            analysis_repo = AnalysisRepository(session)
            report_repo = ReportRepository(session)
            audit_logs = AuditLogRepository(session)

            analysis = await analysis_repo.get(analysis_id, org_id=user.org_id if user else None)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            if analysis.status not in _REPORTABLE_ANALYSIS_STATUSES:
                raise HTTPException(status_code=400, detail="Analysis not yet completed")

            report = await report_repo.get_by_analysis(analysis_id, org_id=user.org_id if user else None)
            if not report:
                report = await report_repo.create(
                    analysis_id,
                    _report_payload(analysis),
                    governance_summary=_governance_summary(analysis),
                    human_review_required=getattr(analysis, "human_review_required", True),
                )

            report_data = _report_payload(analysis)
            html = generate_html_report(report_data, report_id=report.id[:12])
            pdf_bytes = generate_pdf_report(report_data, report_id=report.id[:12])
            artifact_bytes = pdf_bytes if pdf_bytes else html.encode("utf-8")
            artifact_kind = "pdf" if pdf_bytes else "html"
            artifact_content_type = "application/pdf" if pdf_bytes else "text/html; charset=utf-8"

            storage = get_storage_backend()
            stored = storage.store_bytes(
                category="reports",
                filename=f"{report.id}.{artifact_kind}",
                data=artifact_bytes,
                content_type=artifact_content_type,
                metadata={
                    "report_id": report.id,
                    "analysis_id": analysis_id,
                    "artifact_kind": artifact_kind,
                },
                object_name=f"{report.id}-v{report.version}",
            )
            retention_until = datetime.now(timezone.utc) + timedelta(days=settings.REPORT_ARTIFACT_RETENTION_DAYS)
            await report_repo.attach_artifact(
                report.id,
                artifact_path=stored.uri,
                artifact_kind=artifact_kind,
                artifact_content_type=artifact_content_type,
                artifact_size_bytes=stored.size_bytes,
                artifact_checksum_sha256=stored.checksum_sha256,
                retention_until=retention_until,
                pdf_path=stored.uri if artifact_kind == "pdf" else None,
            )
            await audit_logs.create(
                org_id=user.org_id if user else None,
                actor_id=user.user_id if user else "anonymous",
                action="report.artifact_generated",
                resource_type="report",
                resource_id=report.id,
                metadata_json={"artifact_kind": artifact_kind, "artifact_path": stored.uri},
                analysis_id=analysis_id,
            )
            token = create_artifact_token(
                report_id=report.id,
                org_id=user.org_id if user else None,
                artifact_path=stored.uri,
                artifact_content_type=artifact_content_type,
            )

            return {
                "analysis_id": analysis_id,
                "report_id": report.id,
                "artifact_kind": artifact_kind,
                "artifact_content_type": artifact_content_type,
                "artifact_path": stored.uri,
                "artifact_download_url": f"/api/reports/artifacts/{token}",
                "retention_until": retention_until.isoformat(),
            }
    except ImportError:
        raise HTTPException(status_code=503, detail="Artifact generation services not available")
    except Exception as e:
        log.error("Report artifact generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Report artifact generation failed")


@router.get("/artifacts/{token}")
async def download_report_artifact(token: str):
    try:
        payload = decode_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc

    if payload.get("type") != "report_artifact":
        raise HTTPException(status_code=400, detail="Invalid artifact token")

    from services.storage_service import get_storage_backend

    storage = get_storage_backend()
    artifact_bytes = storage.read_bytes(payload["artifact_path"])
    extension = (
        "pdf" if payload["artifact_content_type"].startswith("application/pdf")
        else "html"
    )
    return Response(
        content=artifact_bytes,
        media_type=payload["artifact_content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{payload["sub"]}.{extension}"'
        },
    )
