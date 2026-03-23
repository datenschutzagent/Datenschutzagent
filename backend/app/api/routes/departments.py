"""Departments (organisation units) from configurable YAML."""
from fastapi import APIRouter

from app.config import settings
from app.services.departments_loader import departments_for_api

router = APIRouter()


@router.get("", response_model=list[dict])
async def list_departments():
    """
    List organisation units for case creation and playbook assignment.
    Source: DEPARTMENTS_CONFIG_PATH, or org_profiles/{ORG_PROFILE}/departments.yaml, or legacy fachbereiche.yaml.
    """
    return departments_for_api(settings)
