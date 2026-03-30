"""
ARQ background worker for satellite analysis jobs.

Runs the 5-agent pipeline asynchronously, storing results to the database.
Falls back to inline execution in DEMO_MODE when Redis is unavailable.
"""

import logging
from datetime import datetime, timezone

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
        await repo.update_status(analysis_id, "running")

        sequence = 0
        last_agent_results = {}

        try:
            async for event in run_satellite_pipeline(
                image_bytes=image_bytes,
                image_mime=image_mime,
                norad_id=norad_id,
                additional_context=additional_context,
            ):
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

                agent = event_data.get("agent", "")
                status = event_data.get("status", "")
                payload = event_data.get("payload", {})
                degraded = event_data.get("degraded", False)

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

            # Mark analysis as completed
            insurance_result = last_agent_results.get("insurance_risk", {})
            await repo.update_status(
                analysis_id,
                "completed",
                evidence_gaps=insurance_result.get("evidence_gaps", []),
                report_completeness=insurance_result.get("report_completeness", "COMPLETE"),
            )

            log.info("Analysis completed", extra={"analysis_id": analysis_id})
            return {"status": "completed", "analysis_id": analysis_id}

        except Exception as e:
            log.error("Analysis failed", extra={"analysis_id": analysis_id}, exc_info=True)
            await repo.update_status(analysis_id, "failed")
            return {"status": "failed", "analysis_id": analysis_id, "error": str(e)}


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
