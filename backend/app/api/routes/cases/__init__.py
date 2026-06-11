"""Case management API.

Split into themed sub-routers. ``crud`` holds the core CRUD endpoints (including
the collection-level fixed paths like ``/running-checks`` and ``/export`` that
must precede the greedy ``/{case_id}`` routes); the themed sub-routers (run-checks,
VVT) are appended to it. The resulting ``router`` preserves the original paths.
"""

from app.api.routes.cases import checks, crud, vvt

# Append themed sub-routers to the CRUD router. Their routes only live under
# ``/{case_id}/…`` so they never collide with the collection-level paths.
crud.router.include_router(checks.router)
crud.router.include_router(vvt.router)

router = crud.router

__all__ = ["router"]
