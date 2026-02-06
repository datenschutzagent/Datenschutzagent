"""API package."""
from fastapi import APIRouter

from app.api.routes import cases, documents, findings, playbooks

router = APIRouter()

router.include_router(cases.router, prefix="/cases", tags=["cases"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(findings.router, prefix="/findings", tags=["findings"])
router.include_router(playbooks.router, prefix="/playbooks", tags=["playbooks"])
