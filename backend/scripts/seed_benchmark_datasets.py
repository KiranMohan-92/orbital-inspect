#!/usr/bin/env python3
"""CLI script to seed known benchmark datasets into the dataset registry.

Usage:
    cd backend && python -m scripts.seed_benchmark_datasets

Safe to run repeatedly — uses upsert semantics.
"""

import asyncio
import os
import sys

# Ensure backend/ is on the path when run as a module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GEMINI_API_KEY", "unused-for-seeding")

from config import settings  # noqa: E402
from db.base import async_session_factory, engine, Base  # noqa: E402
from services.dataset_registry_service import seed_benchmark_datasets, KNOWN_BENCHMARKS  # noqa: E402


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"Seeding {len(KNOWN_BENCHMARKS)} benchmark datasets ...")
    async with async_session_factory() as session:
        results = await seed_benchmark_datasets(session)

    print(f"\nRegistered {len(results)} datasets:")
    for item in results:
        print(f"  [{item['dataset_type']}] {item['name']} v{item['version']} — {item['intended_use']}")

    print("\nDone. Benchmark datasets are registered for offline evaluation only.")


if __name__ == "__main__":
    asyncio.run(main())
