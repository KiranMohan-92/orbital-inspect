"""Tests for Gemini service integration helpers."""

from types import SimpleNamespace

import pytest

from services import gemini_service


class _FakePart:
    def __init__(self, text: str):
        self.text = text


class _FakeEvent:
    def __init__(self, text: str):
        self.content = SimpleNamespace(parts=[_FakePart(text)])

    def is_final_response(self) -> bool:
        return True


class _FakeSessionService:
    def __init__(self):
        self.calls = []

    async def create_session(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id="session-123")


class _FakeRunner:
    last_init = None
    last_run = None

    def __init__(self, **kwargs):
        type(self).last_init = kwargs

    async def run_async(self, **kwargs):
        type(self).last_run = kwargs
        yield _FakeEvent(
            '{"valid": true, "satellite_type": "communications", '
            '"orbital_regime": "LEO", "expected_components": ["solar_array"]}'
        )


@pytest.mark.asyncio
async def test_run_adk_agent_awaits_async_session_creation(monkeypatch):
    session_service = _FakeSessionService()

    monkeypatch.setattr(gemini_service, "_ADK_AVAILABLE", True)
    monkeypatch.setattr(gemini_service, "_session_service", session_service)
    monkeypatch.setattr(gemini_service, "Runner", _FakeRunner)

    agent = SimpleNamespace(instruction="Return JSON", model="gemini-2.0-flash")

    result = await gemini_service.run_adk_agent(agent, "classify this")

    assert result["satellite_type"] == "communications"
    assert session_service.calls[0]["app_name"] == gemini_service.APP_NAME
    assert _FakeRunner.last_run["session_id"] == "session-123"


@pytest.mark.asyncio
async def test_run_fallback_raises_when_client_missing(monkeypatch):
    monkeypatch.setattr(gemini_service, "client", None)

    with pytest.raises(RuntimeError, match="No Gemini client available"):
        await gemini_service._run_fallback(SimpleNamespace(instruction="", model="gemini-2.0-flash"), "hello")
