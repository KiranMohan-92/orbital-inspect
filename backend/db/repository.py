"""
Repository pattern for database access.

Isolates SQLAlchemy queries from business logic. All methods are async.
"""

import hashlib
from datetime import datetime, timezone
from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import (
    Analysis,
    AnalysisEvent,
    Report,
    Organization,
    WebhookEndpoint,
    DeadLetterJob,
    WebhookDelivery,
    AuditLog,
)


class AnalysisRepository:
    """CRUD operations for satellite analyses."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        org_id: str | None = None,
        image_bytes: bytes | None = None,
        image_path: str | None = None,
        norad_id: str | None = None,
        additional_context: str = "",
        request_id: str | None = None,
        asset_type: str = "satellite",
        inspection_epoch: str | None = None,
        target_subsystem: str | None = None,
        capture_metadata: dict | None = None,
        telemetry_summary: dict | None = None,
        baseline_reference: dict | None = None,
        evidence_bundle_summary: dict | None = None,
        evidence_completeness_pct: float | None = None,
        queue_name: str = "arq:queue",
        dispatch_mode: str = "inline",
        max_retries: int = 3,
        governance_policy_version: str = "2026-04-03",
        model_manifest: dict | None = None,
        human_review_required: bool = True,
    ) -> Analysis:
        """Create a new analysis record."""
        image_hash = hashlib.sha256(image_bytes).hexdigest() if image_bytes else None

        analysis = Analysis(
            org_id=org_id,
            image_hash=image_hash,
            image_path=image_path,
            norad_id=norad_id,
            additional_context=additional_context,
            request_id=request_id,
            asset_type=asset_type,
            inspection_epoch=inspection_epoch,
            target_subsystem=target_subsystem,
            capture_metadata=capture_metadata or {},
            telemetry_summary=telemetry_summary or {},
            baseline_reference=baseline_reference or {},
            evidence_bundle_summary=evidence_bundle_summary or {},
            evidence_completeness_pct=evidence_completeness_pct,
            queue_name=queue_name,
            dispatch_mode=dispatch_mode,
            max_retries=max_retries,
            governance_policy_version=governance_policy_version,
            model_manifest=model_manifest or {},
            human_review_required=human_review_required,
            status="queued",
            queued_at=datetime.now(timezone.utc),
        )
        self.session.add(analysis)
        await self.session.commit()
        await self.session.refresh(analysis)
        return analysis

    async def get(self, analysis_id: str, org_id: str | None = None) -> Analysis | None:
        """Get analysis by ID."""
        query = select(Analysis).where(Analysis.id == analysis_id)
        if org_id:
            query = query.where(Analysis.org_id == org_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_queue_job_id(self, queue_job_id: str) -> Analysis | None:
        result = await self.session.execute(
            select(Analysis).where(Analysis.queue_job_id == queue_job_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        analysis_id: str,
        status: str,
        **kwargs,
    ) -> None:
        """Update analysis status and optional fields."""
        values = {"status": status}
        if status == "dispatched":
            values.setdefault("queued_at", datetime.now(timezone.utc))
        elif status == "running":
            values["started_at"] = datetime.now(timezone.utc)
        elif status == "retrying":
            values["last_retry_at"] = datetime.now(timezone.utc)
        elif status in ("completed", "completed_partial", "failed", "rejected"):
            values["completed_at"] = datetime.now(timezone.utc)
        values.update(kwargs)

        await self.session.execute(
            update(Analysis).where(Analysis.id == analysis_id).values(**values)
        )
        await self.session.commit()

    async def mark_dispatched(
        self,
        analysis_id: str,
        *,
        queue_job_id: str,
        dispatch_mode: str,
        queue_name: str,
    ) -> None:
        await self.update_status(
            analysis_id,
            "dispatched",
            queue_job_id=queue_job_id,
            dispatch_mode=dispatch_mode,
            queue_name=queue_name,
        )

    async def mark_retry(
        self,
        analysis_id: str,
        *,
        retry_count: int,
        error_message: str,
    ) -> None:
        await self.update_status(
            analysis_id,
            "retrying",
            retry_count=retry_count,
            last_error=error_message,
        )

    async def store_agent_result(
        self,
        analysis_id: str,
        agent_name: str,
        result_data: dict,
    ) -> None:
        """Store an individual agent's result."""
        column_map = {
            "orbital_classification": "classification_result",
            "satellite_vision": "vision_result",
            "orbital_environment": "environment_result",
            "failure_mode": "failure_mode_result",
            "insurance_risk": "insurance_risk_result",
        }
        column = column_map.get(agent_name)
        if column:
            await self.session.execute(
                update(Analysis)
                .where(Analysis.id == analysis_id)
                .values(**{column: result_data})
            )
            await self.session.commit()

    async def store_event(
        self,
        analysis_id: str,
        agent: str,
        status: str,
        payload: dict,
        sequence: int = 0,
        degraded: bool = False,
    ) -> AnalysisEvent:
        """Store an SSE event for audit trail."""
        event = AnalysisEvent(
            analysis_id=analysis_id,
            agent=agent,
            status=status,
            payload=payload,
            sequence=sequence,
            degraded=degraded,
        )
        self.session.add(event)
        await self.session.commit()
        return event

    async def get_events(self, analysis_id: str) -> list[AnalysisEvent]:
        """Get all events for an analysis, ordered by sequence."""
        result = await self.session.execute(
            select(AnalysisEvent)
            .where(AnalysisEvent.analysis_id == analysis_id)
            .order_by(AnalysisEvent.sequence)
        )
        return list(result.scalars().all())

    async def list_analyses(
        self,
        org_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Analysis], int]:
        """List analyses with pagination. Returns (items, total_count)."""
        query = select(Analysis).order_by(Analysis.created_at.desc())
        count_query = select(func.count(Analysis.id))

        if org_id:
            query = query.where(Analysis.org_id == org_id)
            count_query = count_query.where(Analysis.org_id == org_id)

        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query.limit(limit).offset(offset))
        items = list(result.scalars().all())

        return items, total

    async def list_dead_letters(
        self,
        org_id: str | None = None,
        limit: int = 50,
    ) -> list[DeadLetterJob]:
        query = select(DeadLetterJob).order_by(DeadLetterJob.created_at.desc()).limit(limit)
        if org_id:
            query = query.join(Analysis).where(Analysis.org_id == org_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class ReportRepository:
    """CRUD operations for condition reports."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        analysis_id: str,
        full_report: dict,
        *,
        governance_summary: dict | None = None,
        human_review_required: bool = True,
    ) -> Report:
        """Create a draft report from analysis results."""
        report = Report(
            analysis_id=analysis_id,
            full_report_json=full_report,
            status="DRAFT",
            governance_summary=governance_summary or {},
            human_review_required=human_review_required,
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def get(self, report_id: str, org_id: str | None = None) -> Report | None:
        query = select(Report).where(Report.id == report_id)
        if org_id:
            query = query.join(Analysis).where(Analysis.org_id == org_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_analysis(self, analysis_id: str, org_id: str | None = None) -> Report | None:
        query = select(Report).where(Report.analysis_id == analysis_id)
        if org_id:
            query = query.join(Analysis).where(Analysis.org_id == org_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        report_id: str,
        status: str,
        **kwargs,
    ) -> None:
        values = {"status": status, "updated_at": datetime.now(timezone.utc)}
        values.update(kwargs)
        await self.session.execute(
            update(Report).where(Report.id == report_id).values(**values)
        )
        await self.session.commit()

    async def attach_artifact(
        self,
        report_id: str,
        *,
        artifact_path: str,
        artifact_kind: str,
        artifact_content_type: str,
        artifact_size_bytes: int,
        artifact_checksum_sha256: str,
        retention_until,
        pdf_path: str | None = None,
    ) -> None:
        values = {
            "artifact_path": artifact_path,
            "artifact_kind": artifact_kind,
            "artifact_content_type": artifact_content_type,
            "artifact_size_bytes": artifact_size_bytes,
            "artifact_checksum_sha256": artifact_checksum_sha256,
            "retention_until": retention_until,
            "updated_at": datetime.now(timezone.utc),
        }
        if pdf_path is not None:
            values["pdf_path"] = pdf_path
        await self.session.execute(
            update(Report).where(Report.id == report_id).values(**values)
        )
        await self.session.commit()


class WebhookRepository:
    """CRUD operations for persisted webhook endpoints."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        org_id: str | None,
        url: str,
        secret_hash: str,
        secret_ciphertext: str,
        events: list[str],
        active: bool = True,
    ) -> WebhookEndpoint:
        webhook = WebhookEndpoint(
            org_id=org_id,
            url=url,
            secret_hash=secret_hash,
            secret_ciphertext=secret_ciphertext,
            events=events,
            active=active,
        )
        self.session.add(webhook)
        await self.session.commit()
        await self.session.refresh(webhook)
        return webhook

    async def list_for_org(self, org_id: str | None) -> list[WebhookEndpoint]:
        query = (
            select(WebhookEndpoint)
            .where(WebhookEndpoint.active == True)
            .order_by(WebhookEndpoint.created_at.desc())
        )
        if org_id:
            query = query.where(WebhookEndpoint.org_id == org_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get(self, webhook_id: str, org_id: str | None = None) -> WebhookEndpoint | None:
        query = select(WebhookEndpoint).where(WebhookEndpoint.id == webhook_id)
        if org_id:
            query = query.where(WebhookEndpoint.org_id == org_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete(self, webhook_id: str, org_id: str | None = None) -> bool:
        webhook = await self.get(webhook_id, org_id=org_id)
        if not webhook:
            return False
        await self.session.execute(delete(WebhookEndpoint).where(WebhookEndpoint.id == webhook.id))
        await self.session.commit()
        return True


class OrganizationRepository:
    """Persistence for organizations and API keys."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, org_id: str) -> Organization | None:
        result = await self.session.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()

    async def update_api_key_hash(self, org_id: str, api_key_hash: str) -> None:
        await self.session.execute(
            update(Organization).where(Organization.id == org_id).values(api_key_hash=api_key_hash)
        )
        await self.session.commit()


class DeadLetterRepository:
    """Persistence for dead-lettered jobs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        analysis_id: str,
        job_id: str | None,
        queue_name: str,
        job_name: str,
        attempts: int,
        error_message: str,
        payload_json: dict | None = None,
    ) -> DeadLetterJob:
        item = DeadLetterJob(
            analysis_id=analysis_id,
            job_id=job_id,
            queue_name=queue_name,
            job_name=job_name,
            attempts=attempts,
            error_message=error_message,
            payload_json=payload_json or {},
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item


class WebhookDeliveryRepository:
    """Persistence for webhook delivery attempts."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        webhook_id: str,
        event_type: str,
        success: bool,
        status_code: int | None,
        attempt_count: int,
        response_excerpt: str | None,
        request_body_checksum: str | None,
        delivered_at=None,
    ) -> WebhookDelivery:
        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            event_type=event_type,
            success=success,
            status_code=status_code,
            attempt_count=attempt_count,
            response_excerpt=response_excerpt,
            request_body_checksum=request_body_checksum,
            delivered_at=delivered_at,
        )
        self.session.add(delivery)
        await self.session.commit()
        await self.session.refresh(delivery)
        return delivery


class AuditLogRepository:
    """Persistence for audit trail records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        org_id: str | None,
        actor_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata_json: dict | None = None,
        analysis_id: str | None = None,
    ) -> AuditLog:
        item = AuditLog(
            org_id=org_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata_json or {},
            analysis_id=analysis_id,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def list_for_org(self, org_id: str | None, limit: int = 100) -> list[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if org_id:
            query = query.where(AuditLog.org_id == org_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
