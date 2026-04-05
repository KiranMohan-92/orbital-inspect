"""Backfill decision and triage state for historical analyses."""

import asyncio

from db.base import async_session_factory
from services.post_analysis_service import backfill_decisions


async def _run() -> None:
    async with async_session_factory() as session:
        processed = await backfill_decisions(session=session, limit=5000)
    print(f"backfilled_decisions={processed}")


if __name__ == "__main__":
    asyncio.run(_run())
