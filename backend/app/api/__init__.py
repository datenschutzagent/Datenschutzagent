"""API package."""
from fastapi import APIRouter

from app.api.routes import admin, cases, departments, documents, findings, playbooks, users

router = APIRouter()

router.include_router(users.router, tags=["me"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(cases.router, prefix="/cases", tags=["cases"])
router.include_router(departments.router, prefix="/departments", tags=["departments"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(findings.router, prefix="/findings", tags=["findings"])
router.include_router(playbooks.router, prefix="/playbooks", tags=["playbooks"])
