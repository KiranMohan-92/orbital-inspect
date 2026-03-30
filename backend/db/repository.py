"""
Repository pattern for database access.

Isolates SQLAlchemy queries from business logic. All methods are async.
"""

import hashlib
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Analysis, AnalysisEvent, Report, Organization


class AnalysisRepository:
    """CRUD operations for satellite analyses."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        org_id: str | None = None,
        image_bytes: bytes | None = None,
        norad_id: str | None = None,
        additional_context: str = "",
    ) -> Analysis:
        """Create a new analysis record."""
        image_hash = hashlib.sha256(image_bytes).hexdigest() if image_bytes else None

        analysis = Analysis(
            org_id=org_id,
            image_hash=image_hash,
            norad_id=norad_id,
            additional_context=additional_context,
            status="queued",
        )
        self.session.add(analysis)
        await self.session.commit()
        await self.session.refresh(analysis)
        return analysis

    async def get(self, analysis_id: str) -> Analysis | None:
        """Get analysis by ID."""
        result = await self.session.execute(
            select(Analysis).where(Analysis.id == analysis_id)
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
        if status == "running":
            values["started_at"] = datetime.now(timezone.utc)
        elif status in ("completed", "failed"):
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

    async def get(self, report_id: str) -> Report | None:
        result = await self.session.execute(
            select(Report).where(Report.id == report_id)
        )
        return result.scalar_one_or_none()

    async def get_by_analysis(self, analysis_id: str) -> Report | None:
        result = await self.session.execute(
            select(Report).where(Report.analysis_id == analysis_id)
        )
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
