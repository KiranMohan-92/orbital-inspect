"""
Repository pattern for database access.

Isolates SQLAlchemy queries from business logic. All methods are async.
"""

import hashlib
from datetime import datetime, timezone
from sqlalchemy import select, update, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload
from db.models import (
    Analysis,
    AnalysisEvent,
    Report,
    Organization,
    Asset,
    AssetAlias,
    AssetSubsystem,
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
        asset_id: str | None = None,
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
            asset_id=asset_id,
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
        query = (
            select(Analysis)
            .options(selectinload(Analysis.asset), selectinload(Analysis.subsystem))
            .where(Analysis.id == analysis_id)
        )
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

    async def update_fields(self, analysis_id: str, **values) -> None:
        if not values:
            return
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

    async def update_decision_state(
        self,
        analysis_id: str,
        *,
        decision_summary: dict,
        decision_status: str,
        decision_recommended_action: str | None,
        decision_confidence: str | None,
        decision_urgency: str | None,
        decision_blocked_reason: str | None,
        triage_score: float | None,
        triage_band: str | None,
        triage_factors: dict,
        recurrence_count: int,
        decision_override_reason: str | None = None,
        decision_approved_by: str | None = None,
        decision_approved_at=None,
    ) -> None:
        values = {
            "decision_summary": decision_summary,
            "decision_status": decision_status,
            "decision_recommended_action": decision_recommended_action,
            "decision_confidence": decision_confidence,
            "decision_urgency": decision_urgency,
            "decision_blocked_reason": decision_blocked_reason,
            "triage_score": triage_score,
            "triage_band": triage_band,
            "triage_factors": triage_factors,
            "recurrence_count": recurrence_count,
            "decision_override_reason": decision_override_reason,
            "decision_approved_by": decision_approved_by,
            "decision_approved_at": decision_approved_at,
            "decision_last_evaluated_at": datetime.now(timezone.utc),
        }
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
        query = (
            select(Analysis)
            .options(selectinload(Analysis.asset), selectinload(Analysis.subsystem))
            .order_by(Analysis.created_at.desc())
        )
        count_query = select(func.count(Analysis.id))

        if org_id:
            query = query.where(Analysis.org_id == org_id)
            count_query = count_query.where(Analysis.org_id == org_id)

        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query.limit(limit).offset(offset))
        items = list(result.scalars().all())

        return items, total

    async def list_for_decision_backfill(
        self,
        *,
        org_id: str | None = None,
        limit: int = 500,
    ) -> list[Analysis]:
        query = (
            select(Analysis)
            .where(Analysis.status.in_(("completed", "completed_partial", "failed", "rejected")))
            .where(
                (Analysis.decision_status.is_(None))
                | (Analysis.decision_status == "")
                | (Analysis.decision_status == "pending_policy")
                | (Analysis.decision_summary.is_(None))
            )
            .order_by(Analysis.created_at.asc())
            .limit(limit)
        )
        if org_id:
            query = query.where(Analysis.org_id == org_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    def _current_asset_analysis_query(self, org_id: str | None = None):
        query = (
            select(Analysis, Asset)
            .join(Asset, Asset.current_analysis_id == Analysis.id)
        )
        if org_id:
            query = query.where(Asset.org_id == org_id)
        return query

    async def list_latest_asset_analyses(
        self,
        *,
        org_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        risk_tier: str | None = None,
        decision_status: str | None = None,
        recommended_action: str | None = None,
        urgency: str | None = None,
        degraded_only: bool = False,
    ) -> tuple[list[tuple[Analysis, Asset | None]], int]:
        base = self._current_asset_analysis_query(org_id).options(selectinload(Analysis.subsystem))
        count_query = select(func.count()).select_from(Asset).where(Asset.current_analysis_id.is_not(None))
        if org_id:
            count_query = count_query.where(Asset.org_id == org_id)

        filters = []
        if status:
            filters.append(Analysis.status == status)
        if risk_tier:
            filters.append(Analysis.insurance_risk_result["risk_tier"].as_string() == risk_tier)
        if decision_status:
            filters.append(Analysis.decision_status == decision_status)
        if recommended_action:
            filters.append(Analysis.decision_recommended_action == recommended_action)
        if urgency:
            filters.append(Analysis.decision_urgency == urgency)
        if degraded_only:
            filters.append(Analysis.degraded.is_(True))
        if filters:
            base = base.where(and_(*filters))
            count_query = count_query.select_from(Asset).join(Analysis, Asset.current_analysis_id == Analysis.id).where(and_(*filters))
            if org_id:
                count_query = count_query.where(Asset.org_id == org_id)

        total = (await self.session.execute(count_query)).scalar() or 0
        base = base.order_by(
            Analysis.triage_score.desc().nullslast(),
            func.coalesce(Analysis.completed_at, Analysis.created_at).desc(),
        ).limit(limit).offset(offset)
        result = await self.session.execute(base)
        return list(result.all()), total

    async def get_asset_portfolio_summary(self, *, org_id: str | None = None) -> dict:
        current_query = (
            select(
                Analysis.id.label("analysis_id"),
                Analysis.status.label("status"),
                Analysis.decision_status.label("decision_status"),
                Analysis.decision_recommended_action.label("recommended_action"),
                Analysis.decision_urgency.label("decision_urgency"),
                Analysis.insurance_risk_result["risk_tier"].as_string().label("risk_tier"),
                Analysis.insurance_risk_result["underwriting_recommendation"].as_string().label("underwriting"),
            )
            .join(Asset, Asset.current_analysis_id == Analysis.id)
        )
        if org_id:
            current_query = current_query.where(Asset.org_id == org_id)
        current_analyses = current_query.subquery()

        async def _counts(column):
            result = await self.session.execute(
                select(column, func.count())
                .select_from(current_analyses)
                .where(column.is_not(None))
                .group_by(column)
            )
            return {str(key): int(count) for key, count in result.all() if key is not None}

        total_assets_query = select(func.count(Asset.id)).where(Asset.current_analysis_id.is_not(None))
        if org_id:
            total_assets_query = total_assets_query.where(Asset.org_id == org_id)
        total_assets = (await self.session.execute(total_assets_query)).scalar() or 0

        total_analyses_query = select(func.count(Analysis.id))
        if org_id:
            total_analyses_query = total_analyses_query.where(Analysis.org_id == org_id)
        total_analyses = (await self.session.execute(total_analyses_query)).scalar() or 0
        completed = (
            await self.session.execute(
                select(func.count())
                .select_from(current_analyses)
                .where(current_analyses.c.status.in_(("completed", "completed_partial")))
            )
        ).scalar() or 0

        risk_distribution = await _counts(current_analyses.c.risk_tier)
        underwriting_distribution = await _counts(current_analyses.c.underwriting)
        decision_distribution = await _counts(current_analyses.c.decision_status)
        recommended_action_distribution = await _counts(current_analyses.c.recommended_action)
        urgency_distribution = await _counts(current_analyses.c.decision_urgency)
        status_distribution = await _counts(current_analyses.c.status)
        open_attention_queue = int(
            decision_distribution.get("pending_human_review", 0)
            + decision_distribution.get("blocked", 0)
        )
        urgent_assets = int(urgency_distribution.get("urgent", 0))
        approved_assets = int(decision_distribution.get("approved_for_use", 0))

        return {
            "total_assets": int(total_assets),
            "total_analyses": int(total_analyses),
            "completed": int(completed),
            "status_distribution": status_distribution,
            "risk_distribution": risk_distribution,
            "underwriting_distribution": underwriting_distribution,
            "decision_distribution": decision_distribution,
            "recommended_action_distribution": recommended_action_distribution,
            "urgency_distribution": urgency_distribution,
            "open_attention_queue": open_attention_queue,
            "urgent_assets": urgent_assets,
            "approved_assets": approved_assets,
        }

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


class AssetRepository:
    """Persistence for stable asset identities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, asset_id: str, org_id: str | None = None) -> Asset | None:
        query = select(Asset).where(Asset.id == asset_id)
        if org_id:
            query = query.where(Asset.org_id == org_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def resolve_or_create(
        self,
        *,
        org_id: str | None,
        norad_id: str | None,
        external_asset_id: str | None = None,
        asset_type: str,
        name: str | None = None,
        operator_name: str | None = None,
    ) -> Asset:
        asset = None
        if external_asset_id:
            result = await self.session.execute(
                select(Asset)
                .where(Asset.org_id == org_id)
                .where(Asset.external_asset_id == external_asset_id)
                .where(Asset.asset_type == asset_type)
                .order_by(Asset.created_at.asc())
                .limit(1)
            )
            asset = result.scalar_one_or_none()
            if not asset:
                asset = await self._find_by_alias(
                    org_id=org_id,
                    asset_type=asset_type,
                    alias_type="external_id",
                    alias_value=external_asset_id,
                )

        if not asset and norad_id:
            result = await self.session.execute(
                select(Asset)
                .where(Asset.org_id == org_id)
                .where(Asset.norad_id == norad_id)
                .where(Asset.asset_type == asset_type)
                .order_by(Asset.created_at.asc())
                .limit(1)
            )
            asset = result.scalar_one_or_none()

        if asset:
            dirty = False
            if external_asset_id and not asset.external_asset_id:
                asset.external_asset_id = external_asset_id
                asset.identity_source = asset.identity_source or "external_id"
                dirty = True
            if name and not asset.name:
                asset.name = name
                dirty = True
            if operator_name and not asset.operator_name:
                asset.operator_name = operator_name
                dirty = True
            if dirty:
                await self.session.commit()
                await self.session.refresh(asset)
            await self._register_aliases(
                asset=asset,
                norad_id=norad_id,
                external_asset_id=external_asset_id,
                display_name=name,
            )
            return asset

        asset = Asset(
            org_id=org_id,
            norad_id=norad_id,
            external_asset_id=external_asset_id,
            name=name,
            asset_type=asset_type,
            identity_source=(
                "external_id"
                if external_asset_id
                else "norad"
                if norad_id
                else "label"
                if name
                else "ephemeral"
            ),
            operator_name=operator_name,
            status="active",
        )
        self.session.add(asset)
        await self.session.commit()
        await self.session.refresh(asset)
        await self._register_aliases(
            asset=asset,
            norad_id=norad_id,
            external_asset_id=external_asset_id,
            display_name=name,
        )
        return asset

    async def update_metadata(
        self,
        asset_id: str,
        *,
        norad_id: str | None = None,
        external_asset_id: str | None = None,
        name: str | None = None,
        operator_name: str | None = None,
        status: str | None = None,
        current_analysis_id: str | None = None,
    ) -> None:
        values = {}
        if norad_id is not None:
            values["norad_id"] = norad_id
        if external_asset_id is not None:
            values["external_asset_id"] = external_asset_id
        if name is not None:
            values["name"] = name
        if operator_name is not None:
            values["operator_name"] = operator_name
        if status is not None:
            values["status"] = status
        if current_analysis_id is not None:
            values["current_analysis_id"] = current_analysis_id
        if not values:
            return
        values["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(update(Asset).where(Asset.id == asset_id).values(**values))
        await self.session.commit()

    async def promote_current_analysis(
        self,
        *,
        asset_id: str,
        analysis: Analysis,
    ) -> None:
        asset = await self.get(asset_id)
        if not asset:
            return
        if not asset.current_analysis_id:
            await self.update_metadata(asset_id, current_analysis_id=analysis.id)
            return
        if asset.current_analysis_id == analysis.id:
            return

        result = await self.session.execute(
            select(Analysis).where(Analysis.id == asset.current_analysis_id)
        )
        current = result.scalar_one_or_none()
        current_ts = (
            getattr(current, "completed_at", None)
            or getattr(current, "created_at", None)
            or datetime.min.replace(tzinfo=timezone.utc)
        )
        candidate_ts = (
            getattr(analysis, "completed_at", None)
            or getattr(analysis, "created_at", None)
            or datetime.min.replace(tzinfo=timezone.utc)
        )
        if candidate_ts >= current_ts:
            await self.update_metadata(asset_id, current_analysis_id=analysis.id)

    async def resolve_or_create_subsystem(
        self,
        *,
        asset_id: str,
        org_id: str | None,
        subsystem_key: str | None,
        display_name: str | None = None,
        subsystem_type: str | None = None,
    ) -> AssetSubsystem | None:
        key = (subsystem_key or "").strip().lower()
        if not key:
            return None
        result = await self.session.execute(
            select(AssetSubsystem)
            .where(AssetSubsystem.asset_id == asset_id)
            .where(AssetSubsystem.subsystem_key == key)
            .order_by(AssetSubsystem.created_at.asc())
            .limit(1)
        )
        subsystem = result.scalar_one_or_none()
        if subsystem:
            dirty = False
            if display_name and not subsystem.display_name:
                subsystem.display_name = display_name
                dirty = True
            if subsystem_type and not subsystem.subsystem_type:
                subsystem.subsystem_type = subsystem_type
                dirty = True
            if dirty:
                await self.session.commit()
                await self.session.refresh(subsystem)
            return subsystem

        subsystem = AssetSubsystem(
            asset_id=asset_id,
            org_id=org_id,
            subsystem_key=key,
            display_name=display_name or subsystem_key,
            subsystem_type=subsystem_type or key,
            status="active",
        )
        self.session.add(subsystem)
        await self.session.commit()
        await self.session.refresh(subsystem)
        return subsystem

    async def count_prior_attentionworthy_analyses(
        self,
        *,
        asset_id: str,
        current_analysis_id: str,
    ) -> int:
        attentionworthy = (
            select(func.count(Analysis.id))
            .where(Analysis.asset_id == asset_id)
            .where(Analysis.id != current_analysis_id)
            .where(Analysis.status.in_(("completed", "completed_partial")))
            .where(
                (Analysis.decision_recommended_action.in_(("reimage", "maneuver_review", "servicing_candidate", "insurance_escalation", "disposal_review")))
                | (Analysis.decision_status == "blocked")
                | (Analysis.report_completeness == "PARTIAL")
            )
        )
        result = await self.session.execute(attentionworthy)
        return int(result.scalar() or 0)

    async def _find_by_alias(
        self,
        *,
        org_id: str | None,
        asset_type: str,
        alias_type: str,
        alias_value: str,
    ) -> Asset | None:
        result = await self.session.execute(
            select(Asset)
            .join(AssetAlias, AssetAlias.asset_id == Asset.id)
            .where(Asset.org_id == org_id)
            .where(Asset.asset_type == asset_type)
            .where(AssetAlias.alias_type == alias_type)
            .where(AssetAlias.alias_value == alias_value)
            .order_by(Asset.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _register_aliases(
        self,
        *,
        asset: Asset,
        norad_id: str | None,
        external_asset_id: str | None,
        display_name: str | None,
    ) -> None:
        if norad_id:
            await self.upsert_alias(
                asset_id=asset.id,
                org_id=asset.org_id,
                alias_type="norad",
                alias_value=norad_id,
                is_primary=True,
            )
        if external_asset_id:
            await self.upsert_alias(
                asset_id=asset.id,
                org_id=asset.org_id,
                alias_type="external_id",
                alias_value=external_asset_id,
                is_primary=True,
            )
        if display_name:
            await self.upsert_alias(
                asset_id=asset.id,
                org_id=asset.org_id,
                alias_type="display_name",
                alias_value=display_name.strip(),
                is_primary=bool(asset.name and asset.name.strip() == display_name.strip()),
            )

    async def upsert_alias(
        self,
        *,
        asset_id: str,
        org_id: str | None,
        alias_type: str,
        alias_value: str,
        is_primary: bool = False,
    ) -> None:
        value = alias_value.strip()
        if not value:
            return
        result = await self.session.execute(
            select(AssetAlias)
            .where(AssetAlias.asset_id == asset_id)
            .where(AssetAlias.alias_type == alias_type)
            .where(AssetAlias.alias_value == value)
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            if is_primary and not existing.is_primary:
                existing.is_primary = True
                await self.session.commit()
            return
        alias = AssetAlias(
            asset_id=asset_id,
            org_id=org_id,
            alias_type=alias_type,
            alias_value=value,
            is_primary=is_primary,
        )
        self.session.add(alias)
        await self.session.commit()


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
