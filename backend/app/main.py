"""FastAPI application entry point."""
import logging
import logging.config
import urllib.request
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select


def _configure_logging() -> None:
    """Configure JSON structured logging for production; plain text when DEBUG=true."""
    try:
        from pythonjsonlogger.json import JsonFormatter  # type: ignore[import-untyped]
        json_available = True
    except ImportError:
        json_available = False

    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    handler = logging.StreamHandler()

    if json_available:
        handler.setFormatter(
            JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
                rename_fields={"levelname": "level", "asctime": "timestamp", "name": "logger"},
                defaults={"request_id": "-"},
            )
        )
    else:
        handler.setFormatter(logging.Formatter(fmt))

    logging.basicConfig(
        level=logging.DEBUG if _settings_debug() else logging.INFO,
        handlers=[handler],
        force=True,
    )
    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _settings_debug() -> bool:
    """Read DEBUG from env without importing settings (avoids circular import)."""
    import os
    return os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

_configure_logging()

from app.config import settings
from app.core.rate_limit import limiter
from app.core.request_id import RequestIDMiddleware
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


_OPENAPI_TAGS = [
    {"name": "cases", "description": "Datenschutz-Vorgänge verwalten (erstellen, bearbeiten, archivieren, Prüfungen ausführen)."},
    {"name": "documents", "description": "Dokumente hochladen, herunterladen und Textextraktion verwalten."},
    {"name": "findings", "description": "Prüfergebnisse (Findings) einsehen, bewerten und kommentieren."},
    {"name": "playbooks", "description": "Prüfkataloge (Playbooks) erstellen, versionieren und aktivieren."},
    {"name": "legal-bases", "description": "Rechtsgrundlagen-Bibliothek (DSGVO, BDSG, sektoral) verwalten."},
    {"name": "admin", "description": "Systemkonfiguration und Nutzer­verwaltung (nur Admins)."},
    {"name": "me", "description": "Eigenes Nutzerprofil und Präferenzen."},
    {"name": "auth", "description": "OIDC-Konfiguration für das Frontend (öffentlich)."},
    {"name": "config", "description": "Öffentliche App-Konfiguration (Organisationsname, Optionen)."},
    {"name": "departments", "description": "Abteilungsliste der Organisation."},
    {"name": "vvt-overview", "description": "VVT-Gesamtübersicht auf Organisationsebene (Art. 30 DSGVO)."},
]

app = FastAPI(
    title=settings.app_name,
    description=(
        "KI-gestützte Datenschutz-Compliance-Plattform. "
        "Verwaltet Vorgänge, Dokumente und automatisierte Playbook-Prüfungen gemäß DSGVO."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=_OPENAPI_TAGS,
)

# Rate limiter state & 429 handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "x-request-id"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """Add security-relevant HTTP response headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    # Content-Security-Policy: restrict sources; adjust if you embed third-party resources
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response

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
