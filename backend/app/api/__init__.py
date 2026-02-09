"""API package. All /api/v1 routes require authentication when OIDC is enabled."""
from fastapi import APIRouter, Depends

from app.api.routes import admin, admin_prompt_templates, cases, departments, documents, findings, legal_bases, playbooks, users, vvt_overview
from app.core.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

router.include_router(users.router, tags=["me"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(admin_prompt_templates.router, prefix="/admin/prompt-templates", tags=["admin"])
router.include_router(cases.router, prefix="/cases", tags=["cases"])
router.include_router(departments.router, prefix="/departments", tags=["departments"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(findings.router, prefix="/findings", tags=["findings"])
router.include_router(legal_bases.router, prefix="/legal-bases", tags=["legal-bases"])
router.include_router(playbooks.router, prefix="/playbooks", tags=["playbooks"])
router.include_router(vvt_overview.router, prefix="/vvt-overview", tags=["vvt-overview"])
