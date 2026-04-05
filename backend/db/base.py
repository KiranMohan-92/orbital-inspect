"""
Database engine and session factory.

Supports async SQLAlchemy with both PostgreSQL (production) and SQLite (demo mode).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings


class Base(DeclarativeBase):
    pass


def _normalized_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgresql://") and "+asyncpg" not in raw_url:
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw_url


DATABASE_URL = _normalized_database_url(settings.DATABASE_URL)

engine_kwargs = {
    "echo": settings.LOG_LEVEL == "DEBUG",
    "pool_pre_ping": True,
}
if DATABASE_URL.startswith("sqlite") and "uri=true" in DATABASE_URL:
    engine_kwargs["connect_args"] = {"uri": True}
elif not DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
        }
    )

engine = create_async_engine(
    DATABASE_URL,
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
    """Create all tables for demo, E2E, or ephemeral service-backed environments."""
    # Import ORM models before create_all so metadata is fully registered.
    from db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if DATABASE_URL.startswith("sqlite"):
            await _ensure_sqlite_schema(conn)
        else:
            await conn.execute(text("SELECT 1"))


async def _ensure_sqlite_schema(conn) -> None:
    """Best-effort additive schema updates for the demo SQLite database."""
    desired_columns = {
        "assets": {
            "external_asset_id": "ALTER TABLE assets ADD COLUMN external_asset_id VARCHAR(255)",
            "identity_source": "ALTER TABLE assets ADD COLUMN identity_source VARCHAR(32) DEFAULT 'norad'",
            "current_analysis_id": "ALTER TABLE assets ADD COLUMN current_analysis_id VARCHAR(32)",
        },
        "analyses": {
            "asset_id": "ALTER TABLE analyses ADD COLUMN asset_id VARCHAR(32)",
            "subsystem_id": "ALTER TABLE analyses ADD COLUMN subsystem_id VARCHAR(32)",
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
            "queue_job_id": "ALTER TABLE analyses ADD COLUMN queue_job_id VARCHAR(64)",
            "queue_name": "ALTER TABLE analyses ADD COLUMN queue_name VARCHAR(128) DEFAULT 'arq:queue'",
            "dispatch_mode": "ALTER TABLE analyses ADD COLUMN dispatch_mode VARCHAR(20) DEFAULT 'inline'",
            "retry_count": "ALTER TABLE analyses ADD COLUMN retry_count INTEGER DEFAULT 0",
            "max_retries": "ALTER TABLE analyses ADD COLUMN max_retries INTEGER DEFAULT 3",
            "last_error": "ALTER TABLE analyses ADD COLUMN last_error TEXT",
            "last_retry_at": "ALTER TABLE analyses ADD COLUMN last_retry_at DATETIME",
            "governance_policy_version": "ALTER TABLE analyses ADD COLUMN governance_policy_version VARCHAR(32) DEFAULT '2026-04-03'",
            "model_manifest": "ALTER TABLE analyses ADD COLUMN model_manifest JSON DEFAULT '{}'",
            "human_review_required": "ALTER TABLE analyses ADD COLUMN human_review_required BOOLEAN DEFAULT 1",
            "decision_blocked_reason": "ALTER TABLE analyses ADD COLUMN decision_blocked_reason TEXT",
            "decision_summary": "ALTER TABLE analyses ADD COLUMN decision_summary JSON DEFAULT '{}'",
            "decision_status": "ALTER TABLE analyses ADD COLUMN decision_status VARCHAR(32) DEFAULT 'pending_policy'",
            "decision_recommended_action": "ALTER TABLE analyses ADD COLUMN decision_recommended_action VARCHAR(64)",
            "decision_confidence": "ALTER TABLE analyses ADD COLUMN decision_confidence VARCHAR(32)",
            "decision_urgency": "ALTER TABLE analyses ADD COLUMN decision_urgency VARCHAR(32)",
            "decision_approved_by": "ALTER TABLE analyses ADD COLUMN decision_approved_by VARCHAR(255)",
            "decision_approved_at": "ALTER TABLE analyses ADD COLUMN decision_approved_at DATETIME",
            "decision_override_reason": "ALTER TABLE analyses ADD COLUMN decision_override_reason TEXT",
            "decision_last_evaluated_at": "ALTER TABLE analyses ADD COLUMN decision_last_evaluated_at DATETIME",
            "triage_score": "ALTER TABLE analyses ADD COLUMN triage_score FLOAT",
            "triage_band": "ALTER TABLE analyses ADD COLUMN triage_band VARCHAR(32)",
            "triage_factors": "ALTER TABLE analyses ADD COLUMN triage_factors JSON DEFAULT '{}'",
            "recurrence_count": "ALTER TABLE analyses ADD COLUMN recurrence_count INTEGER DEFAULT 0",
            "queued_at": "ALTER TABLE analyses ADD COLUMN queued_at DATETIME",
        },
        "reports": {
            "artifact_path": "ALTER TABLE reports ADD COLUMN artifact_path VARCHAR(500)",
            "artifact_kind": "ALTER TABLE reports ADD COLUMN artifact_kind VARCHAR(20)",
            "artifact_content_type": "ALTER TABLE reports ADD COLUMN artifact_content_type VARCHAR(100)",
            "artifact_size_bytes": "ALTER TABLE reports ADD COLUMN artifact_size_bytes INTEGER",
            "artifact_checksum_sha256": "ALTER TABLE reports ADD COLUMN artifact_checksum_sha256 VARCHAR(64)",
            "retention_until": "ALTER TABLE reports ADD COLUMN retention_until DATETIME",
            "governance_summary": "ALTER TABLE reports ADD COLUMN governance_summary JSON DEFAULT '{}'",
            "human_review_required": "ALTER TABLE reports ADD COLUMN human_review_required BOOLEAN DEFAULT 1",
            "published_at": "ALTER TABLE reports ADD COLUMN published_at DATETIME",
        },
        "webhook_endpoints": {
            "secret_ciphertext": "ALTER TABLE webhook_endpoints ADD COLUMN secret_ciphertext TEXT DEFAULT ''",
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
