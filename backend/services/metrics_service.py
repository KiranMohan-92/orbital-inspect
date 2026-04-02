"""
Lightweight in-process metrics for production diagnostics and E2E verification.

This deliberately avoids an external metrics dependency while still giving the
system counters and latency summaries that can be queried during tests or
staging runs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from threading import Lock


@dataclass
class MetricSummary:
    count: int = 0
    total: float = 0.0
    max: float = 0.0

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.max = max(self.max, value)

    def as_dict(self) -> dict[str, float | int]:
        average = round(self.total / self.count, 2) if self.count else 0.0
        return {
            "count": self.count,
            "avg": average,
            "max": round(self.max, 2),
            "total": round(self.total, 2),
        }


_lock = Lock()
_request_counts: Counter[str] = Counter()
_request_latency: dict[str, MetricSummary] = defaultdict(MetricSummary)
_analysis_counts: Counter[str] = Counter()
_analysis_terminal_counts: Counter[str] = Counter()
_agent_event_counts: Counter[str] = Counter()
_stage_latency: dict[str, MetricSummary] = defaultdict(MetricSummary)
_stream_latency = MetricSummary()
_stream_events = MetricSummary()
_stream_counts: Counter[str] = Counter()
_active_streams = 0


def _key(*parts: str) -> str:
    return "|".join(parts)


def reset_metrics() -> None:
    global _active_streams
    with _lock:
        _request_counts.clear()
        _request_latency.clear()
        _analysis_counts.clear()
        _analysis_terminal_counts.clear()
        _agent_event_counts.clear()
        _stage_latency.clear()
        _stream_latency.count = 0
        _stream_latency.total = 0.0
        _stream_latency.max = 0.0
        _stream_events.count = 0
        _stream_events.total = 0.0
        _stream_events.max = 0.0
        _stream_counts.clear()
        _active_streams = 0


def record_request(method: str, path: str, status: int, duration_ms: float) -> None:
    with _lock:
        count_key = _key(method, path, str(status))
        latency_key = _key(method, path)
        _request_counts[count_key] += 1
        _request_latency[latency_key].add(duration_ms)


def record_analysis_created(asset_type: str) -> None:
    with _lock:
        _analysis_counts[_key("created", asset_type)] += 1


def record_analysis_terminal(status: str) -> None:
    with _lock:
        _analysis_terminal_counts[status] += 1


def record_agent_event(agent: str, status: str, degraded: bool = False) -> None:
    with _lock:
        suffix = "degraded" if degraded else "nominal"
        _agent_event_counts[_key(agent, status, suffix)] += 1


def record_stage_latency(agent: str, duration_ms: float) -> None:
    with _lock:
        _stage_latency[agent].add(duration_ms)


def record_stream_open() -> None:
    global _active_streams
    with _lock:
        _active_streams += 1


def record_stream_close(status: str, duration_ms: float, events_emitted: int) -> None:
    global _active_streams
    with _lock:
        _active_streams = max(0, _active_streams - 1)
        _stream_counts[status] += 1
        _stream_latency.add(duration_ms)
        _stream_events.add(float(events_emitted))


def snapshot_metrics() -> dict[str, object]:
    with _lock:
        return {
            "requests": {
                "counts": dict(_request_counts),
                "latency_ms": {
                    route: summary.as_dict()
                    for route, summary in _request_latency.items()
                },
            },
            "analyses": {
                "created": dict(_analysis_counts),
                "terminal": dict(_analysis_terminal_counts),
                "agent_events": dict(_agent_event_counts),
                "stage_latency_ms": {
                    agent: summary.as_dict()
                    for agent, summary in _stage_latency.items()
                },
            },
            "streams": {
                "active": _active_streams,
                "counts": dict(_stream_counts),
                "duration_ms": _stream_latency.as_dict(),
                "events_per_stream": _stream_events.as_dict(),
            },
        }
