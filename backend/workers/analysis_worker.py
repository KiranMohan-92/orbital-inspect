"""
ARQ background worker for satellite analysis jobs.

Runs the 5-agent pipeline asynchronously, storing results to the database.
Falls back to inline execution in DEMO_MODE when Redis is unavailable.
"""

import logging
import mimetypes
from time import perf_counter

from arq import Retry
from structlog.contextvars import bind_contextvars, clear_contextvars

from services.metrics_service import (
    record_agent_event,
    record_analysis_terminal,
    record_dead_letter,
    record_retry,
    record_stage_latency,
)
from services.observability_service import current_trace_id, setup_observability, shutdown_observability, start_span

log = logging.getLogger(__name__)


async def run_analysis_job(
    ctx: dict,
    analysis_id: str,
) -> dict:
    """
    Execute the satellite inspection pipeline as a background job.

    Stores each agent's result to the database as it completes.
    """
    from db.base import async_session_factory
    from db.repository import AnalysisRepository, DeadLetterRepository, AuditLogRepository
    from agents.orchestrator import run_satellite_pipeline
    from config import settings
    from services.governance_service import apply_decision_governance
    from services.post_analysis_service import post_analysis_complete
    from services.storage_service import get_storage_backend
    from services.webhook_service import dispatch_registered_webhooks

    log.info("Starting analysis job", extra={"analysis_id": analysis_id})
    job_try = int(ctx.get("job_try", 1))
    job_id = ctx.get("job_id")

    async with async_session_factory() as session:
        repo = AnalysisRepository(session)
        dead_letters = DeadLetterRepository(session)
        audit_logs = AuditLogRepository(session)
        analysis = await repo.get(analysis_id)
        if not analysis:
            log.error("Analysis missing for queued job", extra={"analysis_id": analysis_id})
            return {"status": "failed", "analysis_id": analysis_id, "error": "analysis not found"}
        if analysis.status in {"completed", "completed_partial", "failed", "rejected"}:
            return {"status": analysis.status, "analysis_id": analysis_id}

        bind_contextvars(
            analysis_id=analysis_id,
            request_id=getattr(analysis, "request_id", None) if analysis else None,
        )
        await repo.update_status(analysis_id, "running", retry_count=max(0, job_try - 1))

        storage = get_storage_backend()
        image_bytes = storage.read_bytes(analysis.image_path)
        image_mime = (
            (analysis.capture_metadata or {}).get("primary_content_type")
            or mimetypes.guess_type(analysis.image_path or "")[0]
            or "image/jpeg"
        )

        sequence = 0
        last_agent_results = {}
        failure_reasons: list[str] = []
        any_degraded = False
        pipeline_terminal_status = "failed"
        stage_started_at: dict[str, float] = {}

        try:
            with start_span(
                "analysis.run_job",
                attributes={
                    "analysis.id": analysis_id,
                    "analysis.org_id": analysis.org_id,
                    "analysis.asset_type": getattr(analysis, "asset_type", None),
                    "analysis.queue_name": getattr(analysis, "queue_name", None),
                    "analysis.job_id": job_id,
                    "analysis.retry_count": max(0, job_try - 1),
                },
            ):
                bind_contextvars(trace_id=current_trace_id())

                async for event in run_satellite_pipeline(
                    image_bytes=image_bytes,
                    image_mime=image_mime,
                    norad_id=analysis.norad_id,
                    additional_context=analysis.additional_context or "",
                    analysis_id=analysis_id,
                ):
                    event_name = event.get("event", "")

                    # Extract event data from SSE format
                    event_data_str = event.get("data", "{}")
                    if isinstance(event_data_str, str):
                        import json
                        try:
                            event_data = json.loads(event_data_str)
                        except (json.JSONDecodeError, TypeError):
                            continue
                    else:
                        event_data = event_data_str

                    if event_name == "done":
                        pipeline_terminal_status = event_data.get("status", "failed")
                        continue

                    if event_name == "error":
                        failure_reasons.append(event_data.get("error", "Pipeline error"))
                        continue

                    agent = event_data.get("agent", "")
                    status = event_data.get("status", "")
                    payload = event_data.get("payload", {})
                    degraded = event_data.get("degraded", False)
                    any_degraded = any_degraded or degraded
                    if agent and status:
                        record_agent_event(agent, status, degraded=degraded)
                    if agent and status == "thinking":
                        stage_started_at[agent] = perf_counter()
                    elif agent and status in {"complete", "error"}:
                        started = stage_started_at.pop(agent, None)
                        if started is not None:
                            record_stage_latency(agent, (perf_counter() - started) * 1000.0)

                    # Store event for audit trail
                    await repo.store_event(
                        analysis_id=analysis_id,
                        agent=agent,
                        status=status,
                        payload=payload,
                        sequence=sequence,
                        degraded=degraded,
                    )
                    sequence += 1

                    # Store agent result when complete
                    if status == "complete" and agent:
                        last_agent_results[agent] = payload
                        await repo.store_agent_result(analysis_id, agent, payload)
                    elif status == "error":
                        reason = payload.get("reason")
                        if reason:
                            failure_reasons.append(str(reason))

                governed_insurance, governance = apply_decision_governance(
                    last_agent_results.get("insurance_risk", {}),
                    evidence_completeness_pct=getattr(analysis, "evidence_completeness_pct", None),
                    degraded=any_degraded or pipeline_terminal_status == "completed_partial",
                    failure_reasons=failure_reasons,
                )
                if governed_insurance:
                    last_agent_results["insurance_risk"] = governed_insurance
                    await repo.store_agent_result(analysis_id, "insurance_risk", governed_insurance)

                final_degraded = any_degraded or pipeline_terminal_status == "completed_partial"
                insurance_result = last_agent_results.get("insurance_risk", {})
                await repo.update_status(
                    analysis_id,
                    pipeline_terminal_status,
                    degraded=final_degraded,
                    failure_reasons=failure_reasons,
                    evidence_gaps=insurance_result.get("evidence_gaps", []),
                    report_completeness=insurance_result.get("report_completeness", "COMPLETE"),
                    last_error=None,
                    human_review_required=governance.get("human_review_required", True),
                    decision_blocked_reason=governance.get("decision_blocked_reason"),
                )
                await post_analysis_complete(
                    analysis_id=analysis_id,
                    session=session,
                    actor_id="system:worker",
                )
                await audit_logs.create(
                    org_id=analysis.org_id,
                    actor_id="system:worker",
                    action="analysis.completed",
                    resource_type="analysis",
                    resource_id=analysis_id,
                    metadata_json={
                        "status": pipeline_terminal_status,
                        "retry_count": max(0, job_try - 1),
                        "decision_blocked_reason": governance.get("decision_blocked_reason"),
                    },
                    analysis_id=analysis_id,
                )
                await dispatch_registered_webhooks(
                    org_id=analysis.org_id,
                    event_type="analysis.completed",
                    payload={
                        "analysis_id": analysis_id,
                        "status": pipeline_terminal_status,
                        "report_completeness": insurance_result.get("report_completeness", "COMPLETE"),
                    },
                )
                record_analysis_terminal(pipeline_terminal_status)

                log.info("Analysis completed", extra={"analysis_id": analysis_id, "status": pipeline_terminal_status})
                return {"status": pipeline_terminal_status, "analysis_id": analysis_id}

        except Exception as e:
            max_retries = max(1, getattr(analysis, "max_retries", settings.ANALYSIS_JOB_MAX_RETRIES))
            if job_try < max_retries:
                await repo.mark_retry(
                    analysis_id,
                    retry_count=job_try,
                    error_message=str(e),
                )
                await audit_logs.create(
                    org_id=analysis.org_id,
                    actor_id="system:worker",
                    action="analysis.retrying",
                    resource_type="analysis",
                    resource_id=analysis_id,
                    metadata_json={"retry_count": job_try, "error": str(e)},
                    analysis_id=analysis_id,
                )
                record_retry("scheduled")
                raise Retry(defer=settings.ANALYSIS_RETRY_BACKOFF_BASE_SECONDS * (2 ** (job_try - 1)))

            log.error("Analysis failed", extra={"analysis_id": analysis_id}, exc_info=True)
            await repo.update_status(
                analysis_id,
                "failed",
                degraded=True,
                failure_reasons=[str(e)],
                retry_count=job_try,
                last_error=str(e),
            )
            await dead_letters.create(
                analysis_id=analysis_id,
                job_id=job_id,
                queue_name=getattr(analysis, "queue_name", settings.ANALYSIS_QUEUE_NAME),
                job_name="run_analysis_job",
                attempts=job_try,
                error_message=str(e),
                payload_json={"analysis_id": analysis_id},
            )
            await audit_logs.create(
                org_id=analysis.org_id,
                actor_id="system:worker",
                action="analysis.dead_lettered",
                resource_type="analysis",
                resource_id=analysis_id,
                metadata_json={"attempts": job_try, "error": str(e)},
                analysis_id=analysis_id,
            )
            record_dead_letter("analysis_job_failed")
            record_analysis_terminal("failed")
            return {"status": "failed", "analysis_id": analysis_id, "error": str(e)}
        finally:
            clear_contextvars()


# ARQ worker settings
class WorkerSettings:
    """ARQ worker configuration."""
    from config import settings

    functions = [run_analysis_job]
    max_jobs = 3
    job_timeout = 300
    max_tries = settings.ANALYSIS_JOB_MAX_RETRIES

    @staticmethod
    async def on_startup(ctx):
        setup_observability(service_version="0.2.0")
        log.info("ARQ worker starting")

    @staticmethod
    async def on_shutdown(ctx):
        shutdown_observability()
        log.info("ARQ worker shutting down")
