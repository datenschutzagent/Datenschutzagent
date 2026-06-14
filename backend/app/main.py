"""FastAPI application entry point."""

import logging
import logging.config
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
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
                rename_fields={
                    "levelname": "level",
                    "asctime": "timestamp",
                    "name": "logger",
                },
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

_startup_logger = logging.getLogger("app.startup")

from app.api import router as api_router  # noqa: E402
from app.api.routes import app_config as app_config_routes  # noqa: E402
from app.api.routes import auth as auth_routes  # noqa: E402
from app.config import settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.request_id import RequestIDMiddleware, get_request_id  # noqa: E402
from app.database import async_session_factory, init_db  # noqa: E402
from app.models._db.audit import APIAuditLogModel  # noqa: E402
from app.models.db import UserModel  # noqa: E402
from app.services.playbook_import import import_playbooks_from_yaml  # noqa: E402

# Fixed default user ID when CURRENT_USER_ID is not set (must match users.py)
DEFAULT_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    _startup_logger.info(
        "Application starting",
        extra={
            "llm_provider": getattr(settings, "llm_provider", None),
            "storage_backend": settings.storage_backend,
            "oidc_enabled": settings.oidc_enabled,
            "celery_enabled": settings.celery_enabled,
            "debug": settings.debug,
        },
    )
    if not settings.oidc_enabled:
        _startup_logger.warning(
            "SECURITY: OIDC authentication is DISABLED. All API requests will be processed "
            "as the default user without token validation. "
            "Do NOT expose this instance to any network without enabling OIDC_ENABLED=true."
        )
    if settings.debug:
        _startup_logger.warning(
            "SECURITY: DEBUG mode is active. API documentation (/docs, /redoc) is publicly "
            "accessible. Disable DEBUG for production deployments."
        )
    await init_db()
    seed_dir = (
        Path(settings.playbooks_seed_dir) if settings.playbooks_seed_dir else None
    )
    async with async_session_factory() as session:
        try:
            n = await import_playbooks_from_yaml(session, seed_dir)
            if n > 0:
                await session.commit()
                _startup_logger.info("Playbooks seeded from YAML", extra={"count": n})
        except Exception as exc:
            _startup_logger.error("Playbook seeding failed on startup: %s", exc)
            await session.rollback()
        # Ensure default user exists for GET/PATCH /me when CURRENT_USER_ID is unset
        try:
            res = await session.execute(
                select(UserModel).where(UserModel.id == DEFAULT_USER_ID)
            )
            if res.scalar_one_or_none() is None:
                default_user = UserModel(
                    id=DEFAULT_USER_ID,
                    display_name=settings.default_user_display_name,
                    email=None,
                    preferences={"theme": "system", "language": "de"},
                )
                session.add(default_user)
                await session.commit()
                _startup_logger.info(
                    "Default user created", extra={"user_id": str(DEFAULT_USER_ID)}
                )
        except Exception as exc:
            _startup_logger.error("Default user creation failed on startup: %s", exc)
            await session.rollback()
    # OpenTelemetry (optional — activate by setting OTEL_EXPORTER_OTLP_ENDPOINT)
    if settings.otel_exporter_endpoint:
        from app.core.metrics import (
            configure_opentelemetry,
            instrument_fastapi,
            instrument_sqlalchemy,
        )
        from app.database import engine as _db_engine

        if configure_opentelemetry(
            settings.otel_service_name, settings.otel_exporter_endpoint
        ):
            instrument_fastapi(app)
            instrument_sqlalchemy(_db_engine.sync_engine)

    _startup_logger.info("Application startup complete")
    yield
    _startup_logger.info("Application shutting down")


_OPENAPI_TAGS = [
    {
        "name": "cases",
        "description": "Datenschutz-Vorgänge verwalten (erstellen, bearbeiten, archivieren, Prüfungen ausführen).",
    },
    {
        "name": "documents",
        "description": "Dokumente hochladen, herunterladen und Textextraktion verwalten.",
    },
    {
        "name": "findings",
        "description": "Prüfergebnisse (Findings) einsehen, bewerten und kommentieren.",
    },
    {
        "name": "playbooks",
        "description": "Prüfkataloge (Playbooks) erstellen, versionieren und aktivieren.",
    },
    {
        "name": "legal-bases",
        "description": "Rechtsgrundlagen-Bibliothek (DSGVO, BDSG, sektoral) verwalten.",
    },
    {
        "name": "admin",
        "description": "Systemkonfiguration und Nutzer­verwaltung (nur Admins).",
    },
    {"name": "me", "description": "Eigenes Nutzerprofil und Präferenzen."},
    {
        "name": "auth",
        "description": "OIDC-Konfiguration für das Frontend (öffentlich).",
    },
    {
        "name": "config",
        "description": "Öffentliche App-Konfiguration (Organisationsname, Optionen).",
    },
    {"name": "departments", "description": "Abteilungsliste der Organisation."},
    {
        "name": "vvt-overview",
        "description": "VVT-Gesamtübersicht auf Organisationsebene (Art. 30 DSGVO).",
    },
    {
        "name": "dsfa",
        "description": "Datenschutz-Folgenabschätzung (Art. 35 DSGVO) generieren und verwalten.",
    },
    {
        "name": "dsr",
        "description": "Betroffenenrechts-Anfragen (Art. 15–22 DSGVO) erfassen und bearbeiten.",
    },
    {
        "name": "data-breaches",
        "description": "Datenpannen-Management (Art. 33/34 DSGVO) – 72-Stunden-Meldepflicht.",
    },
    {
        "name": "avv",
        "description": "Auftragsverarbeitungsverträge (Art. 28 DSGVO) verwalten.",
    },
    {
        "name": "tom",
        "description": "Technisch-Organisatorische Maßnahmen (Art. 32 DSGVO) – Katalog und Implementierungsstatus.",
    },
    {
        "name": "case-templates",
        "description": "Vorgangs-Vorlagen für häufig wiederkehrende Verarbeitungstätigkeiten.",
    },
]

app = FastAPI(
    title=settings.app_name,
    description=(
        "KI-gestützte Datenschutz-Compliance-Plattform. "
        "Verwaltet Vorgänge, Dokumente und automatisierte Playbook-Prüfungen gemäß DSGVO."
    ),
    version="1.0.0",
    lifespan=lifespan,
    # Disable API docs in production (set DEBUG=true to re-enable for development)
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    openapi_tags=_OPENAPI_TAGS,
)


def _problem_detail(
    status_code: int, detail: str, error_code: str | None = None
) -> JSONResponse:
    """Return an RFC 7807 Problem Details JSON response."""
    body: dict = {
        "status": status_code,
        "detail": detail,
    }
    if error_code:
        body["type"] = f"urn:datenschutzagent:error:{error_code.lower()}"
        body["code"] = error_code
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"Content-Type": "application/problem+json"},
    )


async def _http_exception_handler(request: Request, exc) -> JSONResponse:
    """Map FastAPI HTTPException to RFC 7807 Problem Details format."""
    from app.core.exceptions import ErrorCode

    _status = exc.status_code
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    # Map well-known HTTP status codes to stable error codes.
    _code_map: dict[int, str] = {
        401: ErrorCode.AUTH_TOKEN_INVALID,
        403: ErrorCode.PERMISSION_DENIED,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        503: ErrorCode.AUTH_OIDC_UNAVAILABLE,
    }
    error_code = _code_map.get(_status)
    return _problem_detail(_status, detail, error_code)


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map Pydantic validation errors to RFC 7807 Problem Details."""
    from app.core.exceptions import ErrorCode

    errors = exc.errors()
    detail = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors
    )
    return _problem_detail(422, detail, ErrorCode.VALIDATION_ERROR)


# Rate limiter state & 429 handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# RFC 7807 Problem Details for HTTP and validation errors
from fastapi import HTTPException as _FastAPIHTTPException  # noqa: E402

app.add_exception_handler(_FastAPIHTTPException, _http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, _validation_exception_handler)  # type: ignore[arg-type]

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "x-request-id"],
)


_access_logger = logging.getLogger("app.access")


@app.middleware("http")
async def log_http_requests(request: Request, call_next) -> Response:
    """Minimal HTTP access log (replaces suppressed uvicorn.access). Skips /health."""
    if request.url.path == "/health":
        return await call_next(request)
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    status_code = response.status_code
    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING
    else:
        level = logging.INFO
    _access_logger.log(
        level,
        "%s %s %d",
        request.method,
        request.url.path,
        status_code,
        extra={"duration_ms": duration_ms, "request_id": get_request_id()},
    )
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """Add security-relevant HTTP response headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    # Content-Security-Policy: restrict sources; adjust if you embed third-party resources.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    # HSTS: enforce HTTPS for one year on production deployments. Only emitted when:
    #   - debug mode is off (avoid poisoning localhost browsers during development), AND
    #   - the request arrived via HTTPS (either direct or via a reverse proxy that sets
    #     X-Forwarded-Proto=https). Emitting HSTS on plain-HTTP responses is useless and
    #     masks misconfiguration.
    if not settings.debug:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        is_https = request.url.scheme == "https" or forwarded_proto == "https"
        if is_https:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)
# Public routes (no auth required)
app.include_router(
    auth_routes.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"]
)
app.include_router(
    app_config_routes.router, prefix=settings.api_v1_prefix, tags=["config"]
)


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request) -> Response:
    """Prometheus metrics endpoint (IP-restricted; see METRICS_ALLOWED_IPS config)."""
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics endpoint disabled")

    client_ip = (request.client.host if request.client else "") or ""
    allowed_ips: list[str] = settings.metrics_allowed_ips  # type: ignore[assignment]
    if allowed_ips and client_ip not in allowed_ips:
        raise HTTPException(status_code=403, detail="Forbidden")

    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    from app.core.metrics import db_pool_checkedout, db_pool_total
    from app.database import engine

    # Refresh DB pool gauges just before generating output
    try:
        pool = engine.pool
        db_pool_checkedout.set(pool.checkedout())
        db_pool_total.set(pool.size())
    except Exception:
        pass

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.middleware("http")
async def track_request_metrics(request: Request, call_next) -> Response:
    """Record HTTP request duration in Prometheus histogram."""
    if request.url.path in ("/health", "/metrics"):
        return await call_next(request)
    import time as _time

    from app.core.metrics import http_request_duration_seconds

    start = _time.monotonic()
    response = await call_next(request)
    # Collapse path parameters to avoid high-cardinality label explosion
    # e.g. /api/v1/cases/abc-123 → /api/v1/cases/{id}
    path = request.url.path
    for segment in path.split("/"):
        if len(segment) == 36 and segment.count("-") == 4:
            path = path.replace(segment, "{id}", 1)
    http_request_duration_seconds.labels(
        method=request.method,
        path=path,
        status_code=str(response.status_code),
    ).observe(_time.monotonic() - start)
    return response


_audit_logger = logging.getLogger("app.audit")
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_AUDIT_SKIP_PATHS = frozenset(
    {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}
)


@app.middleware("http")
async def audit_api_mutations(request: Request, call_next) -> Response:
    """Persist a lean audit record for every mutating API call (POST/PUT/PATCH/DELETE).

    Runs fire-and-forget: a DB failure only logs a warning, the response is
    always returned unchanged.  No request body or PII is stored.
    """
    response = await call_next(request)
    if request.method not in _MUTATING_METHODS:
        return response
    if request.url.path in _AUDIT_SKIP_PATHS:
        return response
    # Collapse UUIDs in path segments to {id} – same approach as track_request_metrics
    path = request.url.path
    for segment in path.split("/"):
        if len(segment) == 36 and segment.count("-") == 4:
            path = path.replace(segment, "{id}", 1)
    user = getattr(getattr(request, "state", None), "current_user", None)
    user_id = getattr(user, "id", None)
    try:
        async with async_session_factory() as session:
            session.add(
                APIAuditLogModel(
                    user_id=user_id,
                    endpoint=path,
                    method=request.method,
                    status_code=response.status_code,
                    request_id=get_request_id(),
                )
            )
            await session.commit()
    except Exception:
        _audit_logger.exception("api_audit_log write failed")
    return response


@app.get("/health")
async def health():
    """Health check for load balancers and Docker.
    Checks Ollama (if enabled), Postgres, and Redis. Returns degraded if any are unreachable.
    """
    import asyncio

    from app.services.connection_checks import check_ollama, check_postgres, check_redis

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
        settings.ollama_enabled and ollama_status not in ("ok", "disabled")
    ) or pg_status != "ok"

    # F12: Limit infrastructure details in the health response to avoid
    # exposing internal topology to unauthenticated callers.
    # In debug mode the full breakdown is returned for troubleshooting.
    if settings.debug:
        from app.core.llm import get_circuit_breaker

        cb = get_circuit_breaker()
        return {
            "status": "degraded" if degraded else "ok",
            "ollama": ollama_status,
            "postgres": pg_status,
            "redis": redis_status,
            "llm_circuit_breaker": cb.state,
        }
    return {"status": "degraded" if degraded else "ok"}
