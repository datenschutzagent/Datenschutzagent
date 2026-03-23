"""Async database session and engine."""
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.db import Base

# Use asyncpg; replace postgresql+asyncpg in URL if needed
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
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


# Idempotent schema migrations for existing DBs (create_all does not add columns to existing tables).
# Only ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS; no data-changing UPDATEs.
_SCHEMA_MIGRATIONS = [
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20)",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS source_strategy VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS oidc_sub VARCHAR(500) NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_oidc_sub ON users (oidc_sub) WHERE oidc_sub IS NOT NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'viewer'",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS processing_context VARCHAR(80) NULL",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS special_category_data BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS international_transfer BOOLEAN NOT NULL DEFAULT false",
]


async def init_db() -> None:
    """Create all tables and run idempotent schema migrations. Call on app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _SCHEMA_MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                # Table "users" may not exist on very old DBs; create_all already created it with all columns
                err = str(e).lower()
                if "does not exist" in err and "users" in err:
                    continue
                raise
