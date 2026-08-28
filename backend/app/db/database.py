"""
db/database.py
==============
SQLAlchemy async engine + session factory.
Supports SQLite (POC) and PostgreSQL (production) via DATABASE_URL env var.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.entities import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine creation
# ---------------------------------------------------------------------------

def _build_engine():
    logger.info(
        "[DB] Creating async engine | url=%s",
        settings.DATABASE_URL.split("://")[0] + "://***",  # hide credentials
    )

    # SQLite requires special pool settings for async
    if settings.DATABASE_URL.startswith("sqlite"):
        # Convert sqlite:/// → sqlite+aiosqlite:///
        async_url = settings.DATABASE_URL.replace(
            "sqlite:///", "sqlite+aiosqlite:///"
        )
        logger.info("[DB] SQLite mode | async_url=%s", async_url)
        engine = create_async_engine(
            async_url,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL: expects postgresql+asyncpg://...
        async_url = settings.DATABASE_URL
        if "postgresql://" in async_url and "+asyncpg" not in async_url:
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
        logger.info("[DB] PostgreSQL mode | async_url type=%s", async_url.split("://")[0])
        engine = create_async_engine(
            async_url,
            echo=settings.DEBUG,
            pool_size=10,
            max_overflow=20,
        )

    logger.info("[DB] Async engine created successfully")
    return engine


engine = _build_engine()

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

logger.info("[DB] AsyncSessionLocal factory configured")


# ---------------------------------------------------------------------------
# DB initialisation (called on app startup)
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create all tables if they do not exist."""
    logger.info("[DB] init_db() called — running CREATE TABLE IF NOT EXISTS for all models")
    async with engine.begin() as conn:
        logger.debug("[DB] Acquired engine connection for schema creation")
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[DB] Database schema initialised successfully")


async def drop_db() -> None:
    """Drop all tables — only called in tests."""
    logger.warning("[DB] drop_db() called — DROPPING ALL TABLES")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("[DB] All tables dropped")


# ---------------------------------------------------------------------------
# Dependency injection helper for FastAPI routes
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a transactional async session.

    Usage in route:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
    """
    logger.debug("[DB] Opening new AsyncSession for request")
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("[DB] AsyncSession opened | session_id=%s", id(session))
            yield session
            await session.commit()
            logger.debug("[DB] AsyncSession committed | session_id=%s", id(session))
        except Exception as exc:
            logger.error(
                "[DB] AsyncSession rollback triggered | session_id=%s | error=%s",
                id(session),
                exc,
            )
            await session.rollback()
            raise
        finally:
            logger.debug("[DB] AsyncSession closed | session_id=%s", id(session))


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager version for use outside FastAPI route context (e.g. seeding)."""
    logger.debug("[DB] Opening contextmanager AsyncSession")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            logger.error("[DB] Context session error | rolling back | error=%s", exc)
            await session.rollback()
            raise
        finally:
            logger.debug("[DB] Context AsyncSession closed")
