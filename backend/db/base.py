"""
Database engine and session factory.

Supports async SQLAlchemy with both PostgreSQL (production) and SQLite (demo mode).
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    pool_pre_ping=True,
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
