"""Async database session and engine."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.db import Base

logger = logging.getLogger(__name__)

# Use asyncpg; replace postgresql+asyncpg in URL if needed.
# Tests (APP_ENVIRONMENT=test) run every case on a fresh event loop, but pooled asyncpg
# connections are bound to the loop they were created on — reusing them across loops fails
# with "got Future attached to a different loop". NullPool opens/closes a connection per
# checkout instead; production keeps the regular QueuePool.
if settings.app_environment == "test":
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        settings.database_url, echo=settings.debug, poolclass=NullPool
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_timeout=settings.db_pool_timeout_seconds,
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables that don't exist yet. Schema migrations are handled
    by Alembic (entrypoint.sh runs ``alembic upgrade head`` before uvicorn starts).
    """
    logger.info("Initializing database: creating missing tables via create_all")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialization complete")
