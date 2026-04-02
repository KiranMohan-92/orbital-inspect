"""
ARQ background worker for satellite analysis jobs.

Runs the 5-agent pipeline asynchronously, storing results to the database.
Falls back to inline execution in DEMO_MODE when Redis is unavailable.
"""

import logging
from datetime import datetime, timezone
from time import perf_counter

from structlog.contextvars import bind_contextvars, clear_contextvars

from services.metrics_service import (
    record_agent_event,
    record_analysis_terminal,
    record_stage_latency,
)

log = logging.getLogger(__name__)


async def run_analysis_job(
    ctx: dict,
    analysis_id: str,
    image_bytes: bytes,
    image_mime: str,
    norad_id: str | None,
    additional_context: str,
) -> dict:
    """
    Execute the satellite inspection pipeline as a background job.

    Stores each agent's result to the database as it completes.
    """
    from db.base import async_session_factory
    from db.repository import AnalysisRepository
    from agents.orchestrator import run_satellite_pipeline

    log.info("Starting analysis job", extra={"analysis_id": analysis_id})

    async with async_session_factory() as session:
        repo = AnalysisRepository(session)
        analysis = await repo.get(analysis_id)
        bind_contextvars(
            analysis_id=analysis_id,
            request_id=getattr(analysis, "request_id", None) if analysis else None,
        )
        await repo.update_status(analysis_id, "running")

        sequence = 0
        last_agent_results = {}
        failure_reasons: list[str] = []
        any_degraded = False
        pipeline_terminal_status = "failed"
        stage_started_at: dict[str, float] = {}

        try:
            async for event in run_satellite_pipeline(
                image_bytes=image_bytes,
                image_mime=image_mime,
                norad_id=norad_id,
                additional_context=additional_context,
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

            final_degraded = any_degraded or pipeline_terminal_status == "completed_partial"
            insurance_result = last_agent_results.get("insurance_risk", {})
            await repo.update_status(
                analysis_id,
                pipeline_terminal_status,
                degraded=final_degraded,
                failure_reasons=failure_reasons,
                evidence_gaps=insurance_result.get("evidence_gaps", []),
                report_completeness=insurance_result.get("report_completeness", "COMPLETE"),
            )
            record_analysis_terminal(pipeline_terminal_status)

            log.info("Analysis completed", extra={"analysis_id": analysis_id, "status": pipeline_terminal_status})
            return {"status": pipeline_terminal_status, "analysis_id": analysis_id}

        except Exception as e:
            log.error("Analysis failed", extra={"analysis_id": analysis_id}, exc_info=True)
            await repo.update_status(analysis_id, "failed", degraded=True, failure_reasons=[str(e)])
            record_analysis_terminal("failed")
            return {"status": "failed", "analysis_id": analysis_id, "error": str(e)}
        finally:
            clear_contextvars()


# ARQ worker settings
class WorkerSettings:
    """ARQ worker configuration."""
    functions = [run_analysis_job]
    max_jobs = 3
    job_timeout = 300

    @staticmethod
    async def on_startup(ctx):
        log.info("ARQ worker starting")

    @staticmethod
    async def on_shutdown(ctx):
        log.info("ARQ worker shutting down")
