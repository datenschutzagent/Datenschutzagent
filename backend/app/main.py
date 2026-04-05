"""FastAPI application entry point."""
import urllib.request
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.api import router as api_router
from app.api.routes import auth as auth_routes
from app.api.routes import app_config as app_config_routes
from app.database import init_db, async_session_factory
from app.models.db import UserModel
from app.services.playbook_import import import_playbooks_from_yaml

# Fixed default user ID when CURRENT_USER_ID is not set (must match users.py)
DEFAULT_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    await init_db()
    seed_dir = Path(settings.playbooks_seed_dir) if settings.playbooks_seed_dir else None
    async with async_session_factory() as session:
        try:
            n = await import_playbooks_from_yaml(session, seed_dir)
            if n > 0:
                await session.commit()
        except Exception:
            await session.rollback()
        # Ensure default user exists for GET/PATCH /me when CURRENT_USER_ID is unset
        try:
            res = await session.execute(select(UserModel).where(UserModel.id == DEFAULT_USER_ID))
            if res.scalar_one_or_none() is None:
                default_user = UserModel(
                    id=DEFAULT_USER_ID,
                    display_name=settings.default_user_display_name,
                    email=None,
                    preferences={"theme": "system", "language": "de"},
                )
                session.add(default_user)
                await session.commit()
        except Exception:
            await session.rollback()
    yield
    # Teardown if needed (e.g. close DB pool)


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
# Public routes (no auth required)
app.include_router(auth_routes.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
app.include_router(app_config_routes.router, prefix=settings.api_v1_prefix, tags=["config"])


@app.get("/health")
async def health():
    """Health check for load balancers and Docker.
    Checks Ollama (if enabled), Postgres, and Redis. Returns degraded if any are unreachable.
    """
    from app.services.connection_checks import check_ollama, check_postgres, check_redis
    import asyncio

    ollama_res, pg_res, redis_res = await asyncio.gather(
        check_ollama(),
        check_postgres(),
        check_redis(),
        return_exceptions=True,
    )

    def _status(res) -> str:
        if isinstance(res, Exception):
            return "unreachable"
        return res.get("status", "unknown")

    ollama_status = _status(ollama_res)
    pg_status = _status(pg_res)
    redis_status = _status(redis_res)

    degraded = (
        (settings.ollama_enabled and ollama_status not in ("ok", "disabled"))
        or pg_status != "ok"
    )

    return {
        "status": "degraded" if degraded else "ok",
        "ollama": ollama_status,
        "postgres": pg_status,
        "redis": redis_status,
    }
