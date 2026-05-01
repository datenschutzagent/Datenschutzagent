"""API package. All /api/v1 routes require authentication when OIDC is enabled."""
from fastapi import APIRouter, Depends

from app.api.routes import admin, admin_prompt_templates, cases, departments, documents, findings, legal_bases, playbooks, users, vvt_overview
from app.api.routes import dsfa, dsr, data_breaches, avv, tom, case_templates
from app.api.routes import privacy_policy, webhooks
from app.api.routes import analytics
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
router.include_router(dsfa.router, prefix="/cases", tags=["dsfa"])
router.include_router(dsr.router, prefix="/dsr", tags=["dsr"])
router.include_router(data_breaches.router, prefix="/data-breaches", tags=["data-breaches"])
router.include_router(avv.router, prefix="/avv", tags=["avv"])
router.include_router(tom.router, prefix="/tom", tags=["tom"])
router.include_router(case_templates.router, prefix="/case-templates", tags=["case-templates"])
router.include_router(privacy_policy.router, prefix="/privacy-policies", tags=["privacy-policy"])
router.include_router(webhooks.router, prefix="/admin/webhooks", tags=["admin"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
