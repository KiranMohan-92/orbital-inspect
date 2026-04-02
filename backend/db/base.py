"""
Database engine and session factory.

Supports async SQLAlchemy with both PostgreSQL (production) and SQLite (demo mode).
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings


class Base(DeclarativeBase):
    pass


engine_kwargs = {
    "echo": settings.LOG_LEVEL == "DEBUG",
    "pool_pre_ping": True,
}
if settings.DATABASE_URL.startswith("sqlite") and "uri=true" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"uri": True}

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Dependency for FastAPI endpoints."""
    async with async_session_factory() as session:
        yield session


async def init_db():
    """Create all tables. Used in DEMO_MODE with SQLite."""
    # Import ORM models before create_all so metadata is fully registered.
    from db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.DATABASE_URL.startswith("sqlite"):
            await _ensure_sqlite_schema(conn)


async def _ensure_sqlite_schema(conn) -> None:
    """Best-effort additive schema updates for the demo SQLite database."""
    desired_columns = {
        "analyses": {
            "request_id": "ALTER TABLE analyses ADD COLUMN request_id VARCHAR(64)",
            "asset_type": "ALTER TABLE analyses ADD COLUMN asset_type VARCHAR(50) DEFAULT 'satellite'",
            "inspection_epoch": "ALTER TABLE analyses ADD COLUMN inspection_epoch VARCHAR(64)",
            "target_subsystem": "ALTER TABLE analyses ADD COLUMN target_subsystem VARCHAR(100)",
            "capture_metadata": "ALTER TABLE analyses ADD COLUMN capture_metadata JSON DEFAULT '{}'",
            "telemetry_summary": "ALTER TABLE analyses ADD COLUMN telemetry_summary JSON DEFAULT '{}'",
            "baseline_reference": "ALTER TABLE analyses ADD COLUMN baseline_reference JSON DEFAULT '{}'",
            "degraded": "ALTER TABLE analyses ADD COLUMN degraded BOOLEAN DEFAULT 0",
            "failure_reasons": "ALTER TABLE analyses ADD COLUMN failure_reasons JSON DEFAULT '[]'",
            "evidence_completeness_pct": "ALTER TABLE analyses ADD COLUMN evidence_completeness_pct FLOAT",
            "evidence_bundle_summary": "ALTER TABLE analyses ADD COLUMN evidence_bundle_summary JSON DEFAULT '{}'",
        },
    }

    for table_name, columns in desired_columns.items():
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
        existing = {row[1] for row in result.fetchall()}
        if not existing:
            continue
        for column_name, ddl in columns.items():
            if column_name in existing:
                continue
            await conn.exec_driver_sql(ddl)
