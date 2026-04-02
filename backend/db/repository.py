"""
Repository pattern for database access.

Isolates SQLAlchemy queries from business logic. All methods are async.
"""

import hashlib
from datetime import datetime, timezone
from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Analysis, AnalysisEvent, Report, Organization, WebhookEndpoint


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
            status="queued",
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

    async def update_status(
        self,
        analysis_id: str,
        status: str,
        **kwargs,
    ) -> None:
        """Update analysis status and optional fields."""
        values = {"status": status}
        if status == "running":
            values["started_at"] = datetime.now(timezone.utc)
        elif status in ("completed", "completed_partial", "failed", "rejected"):
            values["completed_at"] = datetime.now(timezone.utc)
        values.update(kwargs)

        await self.session.execute(
            update(Analysis).where(Analysis.id == analysis_id).values(**values)
        )
        await self.session.commit()

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


class ReportRepository:
    """CRUD operations for condition reports."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, analysis_id: str, full_report: dict) -> Report:
        """Create a draft report from analysis results."""
        report = Report(
            analysis_id=analysis_id,
            full_report_json=full_report,
            status="DRAFT",
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


class WebhookRepository:
    """CRUD operations for persisted webhook endpoints."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        org_id: str | None,
        url: str,
        secret_hash: str,
        events: list[str],
        active: bool = True,
    ) -> WebhookEndpoint:
        webhook = WebhookEndpoint(
            org_id=org_id,
            url=url,
            secret_hash=secret_hash,
            events=events,
            active=active,
        )
        self.session.add(webhook)
        await self.session.commit()
        await self.session.refresh(webhook)
        return webhook

    async def list_for_org(self, org_id: str | None) -> list[WebhookEndpoint]:
        query = select(WebhookEndpoint).order_by(WebhookEndpoint.created_at.desc())
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
