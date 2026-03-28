from pydantic import BaseModel, Field
import time


def _now_ms() -> int:
    return int(time.time() * 1000)


class AgentEvent(BaseModel):
    """SSE event emitted by each agent during the analysis pipeline."""
    agent: str  # orchestrator | vision | environment | failure_mode | priority
    status: str  # queued | thinking | complete | error
    payload: dict = {}
    timestamp: int = Field(default_factory=_now_ms)

    @classmethod
    def thinking(cls, agent: str, message: str) -> "AgentEvent":
        return cls(
            agent=agent,
            status="thinking",
            payload={"message": message},
        )

    @classmethod
    def complete(cls, agent: str, payload: dict) -> "AgentEvent":
        return cls(
            agent=agent,
            status="complete",
            payload=payload,
        )

    @classmethod
    def error(cls, agent: str, reason: str) -> "AgentEvent":
        return cls(
            agent=agent,
            status="error",
            payload={"reason": reason},
        )

    @classmethod
    def queued(cls, agent: str) -> "AgentEvent":
        return cls(
            agent=agent,
            status="queued",
            payload={"message": "Waiting in queue"},
        )
