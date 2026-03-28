"""
Gemini + ADK service layer for Orbital Inspect.

Provides ADK-native agent execution with raw Gemini fallback.
Inherited from DeepInspect, adapted for satellite inspection domain.
"""

import json
import uuid
import asyncio
from config import settings

_ADK_AVAILABLE = False

try:
    from google.adk.agents import Agent, ParallelAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools import google_search
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    _ADK_AVAILABLE = True
    print("[GeminiService] Google ADK loaded successfully")
except ImportError as e:
    print(f"[GeminiService] ADK not available ({e}), using raw Gemini fallback")
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
    except ImportError:
        client = None

APP_NAME = "orbital_inspect"

if _ADK_AVAILABLE:
    _session_service = InMemorySessionService()
else:
    _session_service = None


def is_adk_available() -> bool:
    return _ADK_AVAILABLE


def get_model_name() -> str:
    return settings.GEMINI_MODEL


async def run_adk_agent(
    agent: "Agent",
    user_message: str,
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
    session_state: dict | None = None,
) -> dict:
    """Execute an ADK agent and return parsed JSON response."""
    if not _ADK_AVAILABLE:
        return await _run_fallback(agent, user_message, image_bytes, image_mime)

    user_id = f"user_{uuid.uuid4().hex[:8]}"
    session = _session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        state=session_state or {},
    )

    parts = [types.Part.from_text(text=user_message)]
    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))

    message = types.Content(role="user", parts=parts)

    final_text = ""
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=_session_service,
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text += part.text

    return _parse_json_response(final_text)


def _parse_json_response(text: str) -> dict:
    """Extract JSON from agent response, handling markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"error": "Failed to parse agent response", "raw_text": text[:500]}


async def _run_fallback(
    agent: object,
    user_message: str,
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
) -> dict:
    """Fallback using raw google-genai Client. Uses run_in_executor to avoid blocking."""
    instruction = getattr(agent, "instruction", "") or ""
    model_name = getattr(agent, "model", settings.GEMINI_MODEL) or settings.GEMINI_MODEL

    if client is None:
        return {"error": "No Gemini client available"}

    contents_parts = []
    if instruction:
        contents_parts.append(types.Part.from_text(text=instruction))
    contents_parts.append(types.Part.from_text(text=user_message))

    if image_bytes:
        contents_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))

    def _sync_call():
        return client.models.generate_content(
            model=model_name,
            contents=types.Content(role="user", parts=contents_parts),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, _sync_call)
    return _parse_json_response(response.text or "")
