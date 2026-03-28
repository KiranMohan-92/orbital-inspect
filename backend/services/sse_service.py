"""
SSE (Server-Sent Events) service for streaming agent activity to the frontend.

Formats AgentEvent models into SSE-compatible data strings and provides
an async generator pattern for use with sse-starlette's EventSourceResponse.
"""

import json
from models.events import AgentEvent


def format_sse_event(event: AgentEvent) -> dict:
    """
    Format an AgentEvent into the dict shape expected by sse-starlette.

    Returns:
        {"event": "agent_event", "data": "<json string>"}
    """
    return {
        "event": "agent_event",
        "data": event.model_dump_json(),
    }


def format_sse_done() -> dict:
    """Format a terminal 'done' event to signal stream completion."""
    return {
        "event": "done",
        "data": json.dumps({"status": "complete"}),
    }


def format_sse_error(message: str) -> dict:
    """Format a top-level error event (not agent-specific)."""
    return {
        "event": "error",
        "data": json.dumps({"error": message}),
    }


def thinking_event(agent: str, message: str) -> dict:
    """Convenience: create and format a 'thinking' SSE event."""
    return format_sse_event(AgentEvent.thinking(agent, message))


def complete_event(agent: str, payload: dict) -> dict:
    """Convenience: create and format a 'complete' SSE event."""
    return format_sse_event(AgentEvent.complete(agent, payload))


def error_event(agent: str, reason: str) -> dict:
    """Convenience: create and format an 'error' SSE event."""
    return format_sse_event(AgentEvent.error(agent, reason))
