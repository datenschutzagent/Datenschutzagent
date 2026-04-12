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
    # Neue Spalten für vorhandene Installationen
    "ALTER TABLE dsr_requests ADD COLUMN IF NOT EXISTS draft_response TEXT",
    "CREATE INDEX IF NOT EXISTS ix_finding_chat_messages_finding_id ON finding_chat_messages (finding_id)",
    "CREATE INDEX IF NOT EXISTS ix_dsfa_jobs_case_id ON dsfa_jobs (case_id)",
    "CREATE INDEX IF NOT EXISTS ix_dsr_requests_status ON dsr_requests (status)",
    "CREATE INDEX IF NOT EXISTS ix_dsr_requests_response_deadline ON dsr_requests (response_deadline)",
    "CREATE INDEX IF NOT EXISTS ix_dsr_activity_log_request_id ON dsr_activity_log (request_id)",
    # Datenpannen-Management (Art. 33/34 DSGVO)
    "ALTER TABLE data_breaches ADD COLUMN IF NOT EXISTS authority_reference VARCHAR(200)",
    "ALTER TABLE data_breaches ADD COLUMN IF NOT EXISTS draft_notification TEXT",
    # AVV-Management
    "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS check_result JSONB",
    # TOM-Katalog
    "ALTER TABLE tom_measures ADD COLUMN IF NOT EXISTS evidence TEXT",
    # Vorgangs-Vorlagen
    "ALTER TABLE case_templates ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN NOT NULL DEFAULT false",
    # AVV-Risikobewertung (Supplier Risk Scoring)
    "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_score INTEGER",
    "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20)",
    "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_assessment JSONB",
    "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_assessed_at TIMESTAMPTZ",
    # Periodische Re-Checks (CaseModel)
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS recheck_interval_days INTEGER",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_rechecked_at TIMESTAMPTZ",
    # Anti-Spam: Letzter Benachrichtigungsversand pro Entität
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ",
    "ALTER TABLE cases ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
    "ALTER TABLE data_breaches ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ",
    "ALTER TABLE dsr_requests ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ",
    "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ",
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
