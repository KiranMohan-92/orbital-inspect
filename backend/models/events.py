from pydantic import BaseModel, Field
import time
import uuid


def _now_ms() -> int:
    return int(time.time() * 1000)


class AgentEvent(BaseModel):
    """SSE event emitted by each agent during the analysis pipeline."""
    agent: str  # orchestrator | vision | environment | failure_mode | priority
    status: str  # queued | thinking | complete | error
    payload: dict = {}
    timestamp: int = Field(default_factory=_now_ms)
    # v2 fields
    analysis_id: str = ""
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    sequence: int = 0
    schema_version: str = "2.0"
    degraded: bool = False

    @classmethod
    def thinking(
        cls,
        agent: str,
        message: str,
        analysis_id: str = "",
        sequence: int = 0,
        degraded: bool = False,
    ) -> "AgentEvent":
        return cls(
            agent=agent,
            status="thinking",
            payload={"message": message},
            analysis_id=analysis_id,
            sequence=sequence,
            degraded=degraded,
        )

    @classmethod
    def complete(
        cls,
        agent: str,
        payload: dict,
        analysis_id: str = "",
        sequence: int = 0,
        degraded: bool = False,
    ) -> "AgentEvent":
        return cls(
            agent=agent,
            status="complete",
            payload=payload,
            analysis_id=analysis_id,
            sequence=sequence,
            degraded=degraded,
        )

    @classmethod
    def error(
        cls,
        agent: str,
        reason: str,
        analysis_id: str = "",
        sequence: int = 0,
        degraded: bool = False,
    ) -> "AgentEvent":
        return cls(
            agent=agent,
            status="error",
            payload={"reason": reason},
            analysis_id=analysis_id,
            sequence=sequence,
            degraded=degraded,
        )

    @classmethod
    def queued(
        cls,
        agent: str,
        analysis_id: str = "",
        sequence: int = 0,
        degraded: bool = False,
    ) -> "AgentEvent":
        return cls(
            agent=agent,
            status="queued",
            payload={"message": "Waiting in queue"},
            analysis_id=analysis_id,
            sequence=sequence,
            degraded=degraded,
        )
