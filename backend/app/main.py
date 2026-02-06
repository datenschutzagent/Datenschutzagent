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
                    display_name="Standardnutzer",
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
# Auth config is public so frontend can discover OIDC endpoints without a token
app.include_router(auth_routes.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])


@app.get("/health")
def health():
    """Health check for load balancers and Docker. If Ollama is enabled, checks reachability."""
    if not settings.ollama_enabled:
        return {"status": "ok"}
    base = settings.ollama_base_url.rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return {"status": "ok"}
    except Exception:
        return {"status": "degraded", "ollama": "unreachable"}
    return {"status": "degraded", "ollama": "unreachable"}
