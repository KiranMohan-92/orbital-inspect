"""
Shared post-analysis processing for decision and triage persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from db.repository import AnalysisRepository, AssetRepository, AuditLogRepository
from services.decision_policy_service import compute_triage, evaluate_decision_policy
from services.webhook_service import dispatch_registered_webhooks


async def post_analysis_complete(
    *,
    analysis_id: str,
    session,
    actor_id: str = "system:post-analysis",
) -> None:
    analysis_repo = AnalysisRepository(session)
    asset_repo = AssetRepository(session)
    audit_logs = AuditLogRepository(session)

    analysis = await analysis_repo.get(analysis_id)
    if not analysis:
        return

    classification = dict(getattr(analysis, "classification_result", {}) or {})
    baseline_reference = dict(getattr(analysis, "baseline_reference", {}) or {})
    capture_metadata = dict(getattr(analysis, "capture_metadata", {}) or {})
    external_asset_id = (
        baseline_reference.get("external_asset_id")
        or capture_metadata.get("external_asset_id")
        or classification.get("external_asset_id")
    )
    asset_name = (
        baseline_reference.get("asset_name")
        or capture_metadata.get("asset_name")
        or classification.get("name")
    )

    asset = await asset_repo.resolve_or_create(
        org_id=analysis.org_id,
        norad_id=analysis.norad_id,
        external_asset_id=external_asset_id,
        asset_type=getattr(analysis, "asset_type", "satellite"),
        name=asset_name,
        operator_name=classification.get("operator"),
    )
    if getattr(analysis, "asset_id", None) != asset.id:
        await analysis_repo.update_fields(analysis_id, asset_id=asset.id)
        analysis = await analysis_repo.get(analysis_id)
        if not analysis:
            return

    subsystem = await asset_repo.resolve_or_create_subsystem(
        asset_id=asset.id,
        org_id=analysis.org_id,
        subsystem_key=getattr(analysis, "target_subsystem", None),
        display_name=getattr(analysis, "target_subsystem", None),
        subsystem_type=getattr(analysis, "target_subsystem", None),
    )
    if subsystem and getattr(analysis, "subsystem_id", None) != subsystem.id:
        await analysis_repo.update_fields(analysis_id, subsystem_id=subsystem.id)
        analysis = await analysis_repo.get(analysis_id)
        if not analysis:
            return

    await asset_repo.update_metadata(
        asset.id,
        norad_id=analysis.norad_id,
        external_asset_id=external_asset_id,
        name=asset.name or asset_name,
        operator_name=asset.operator_name or classification.get("operator"),
    )

    decision = evaluate_decision_policy(analysis)
    recurrence_count = await asset_repo.count_prior_attentionworthy_analyses(
        asset_id=asset.id,
        current_analysis_id=analysis.id,
    )
    triage_score, triage_band, triage_factors = compute_triage(
        analysis,
        decision_summary=decision.summary,
        decision_status=decision.status,
        recurrence_count=recurrence_count,
    )

    await analysis_repo.update_decision_state(
        analysis_id,
        decision_summary=decision.summary,
        decision_status=decision.status,
        decision_recommended_action=decision.summary.get("recommended_action"),
        decision_confidence=decision.summary.get("decision_confidence"),
        decision_urgency=decision.summary.get("urgency"),
        decision_blocked_reason=decision.summary.get("blocked_reason"),
        triage_score=triage_score,
        triage_band=triage_band,
        triage_factors=triage_factors,
        recurrence_count=recurrence_count,
    )
    await asset_repo.promote_current_analysis(asset_id=asset.id, analysis=analysis)
    await audit_logs.create(
        org_id=analysis.org_id,
        actor_id=actor_id,
        action="analysis.decision_evaluated",
        resource_type="analysis",
        resource_id=analysis_id,
        metadata_json={
            "asset_id": asset.id,
            "subsystem_id": subsystem.id if subsystem else None,
            "decision_status": decision.status,
            "recommended_action": decision.summary.get("recommended_action"),
            "triage_score": triage_score,
            "triage_band": triage_band,
        },
        analysis_id=analysis_id,
    )
    await dispatch_registered_webhooks(
        org_id=analysis.org_id,
        event_type="decision.created",
        payload={
            "analysis_id": analysis_id,
            "asset_id": asset.id,
            "decision_status": decision.status,
            "recommended_action": decision.summary.get("recommended_action"),
            "triage_score": triage_score,
            "triage_band": triage_band,
        },
    )


async def backfill_decisions(
    *,
    session,
    org_id: str | None = None,
    limit: int = 500,
) -> int:
    repo = AnalysisRepository(session)
    analyses = await repo.list_for_decision_backfill(org_id=org_id, limit=limit)
    processed = 0
    for analysis in analyses:
        await post_analysis_complete(
            analysis_id=analysis.id,
            session=session,
            actor_id="system:decision-backfill",
        )
        processed += 1
    return processed


def apply_review_action(
    *,
    current_status: str,
    action: str,
    override_action: str | None = None,
    actor_is_admin: bool = False,
) -> tuple[str, str | None]:
    if current_status not in {"pending_human_review", "approved_for_use", "blocked"}:
        raise ValueError(f"Decision review not allowed from {current_status}")

    if action == "approve":
        if current_status == "blocked":
            raise ValueError("Blocked decisions must be reset before approval")
        return "approved_for_use", None
    if action == "reset_review":
        return "pending_human_review", None
    if action == "block":
        return "blocked", None
    if action == "request_reimage":
        return "blocked", "reimage"
    if action == "override_action":
        if not actor_is_admin:
            raise ValueError("Only admins may override recommended action")
        if current_status == "blocked":
            raise ValueError("Blocked decisions must be reset before override")
        if not override_action:
            raise ValueError("override_action is required")
        return "approved_for_use", override_action
    raise ValueError(f"Unsupported review action: {action}")
