"""Regression test: every non-public FastAPI route must sit behind ``get_current_user``.

Background: new routers are sometimes added at the top level instead of mounting
under ``api_router`` (which applies ``dependencies=[Depends(get_current_user)]``
in ``backend/app/api/__init__.py``). This test iterates the registered routes
and asserts that anything outside an explicit public whitelist inherits the auth
dependency, so that forgetting to mount a router under the authenticated tree is
caught before it reaches production.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.core.auth import get_current_user
from app.main import app


# Paths that are intentionally public. Keep tight — every entry here is an
# unauthenticated surface that must be justified.
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/health",
    "/api/v1/auth/",       # OIDC config, login callback, token exchange
    "/api/v1/config",      # App config for the frontend bootstrap
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",            # Prometheus scrape — protected by METRICS_ALLOWED_IPS, not user auth
)


def _depends_on_current_user(route: APIRoute) -> bool:
    """True if the route (or a router it is mounted under) depends on ``get_current_user``."""
    for dep in route.dependant.dependencies:
        if dep.call is get_current_user:
            return True
        for sub in dep.dependencies:
            if sub.call is get_current_user:
                return True
    return route.dependant.call is get_current_user


def _is_public(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def test_all_non_public_routes_require_authentication() -> None:
    unprotected: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if _is_public(route.path):
            continue
        if not _depends_on_current_user(route):
            unprotected.append(f"{sorted(route.methods)} {route.path}")
    assert not unprotected, (
        "Routes missing get_current_user dependency — add them to the authenticated "
        "router in app/api/__init__.py or to PUBLIC_PATH_PREFIXES if truly public:\n  "
        + "\n  ".join(unprotected)
    )


def test_public_whitelist_contains_only_expected_entries() -> None:
    """Guard against silently broadening the public surface via this test."""
    assert PUBLIC_PATH_PREFIXES == (
        "/health",
        "/api/v1/auth/",
        "/api/v1/config",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
    )
