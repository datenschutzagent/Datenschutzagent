"""API package."""
from fastapi import APIRouter

from app.api.routes import cases, documents

router = APIRouter()

router.include_router(cases.router, prefix="/cases", tags=["cases"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
