"""Findings API (e.g. status updates)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import ActivityLogModel, FindingModel, orm_to_finding_response
from app.models.schemas import FindingResponse, FindingUpdate

router = APIRouter()


@router.patch("/{finding_id}", response_model=FindingResponse)
async def update_finding(
    finding_id: UUID,
    body: FindingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a finding (e.g. status: open, accepted, overruled, fixed)."""
    result = await db.execute(select(FindingModel).where(FindingModel.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    old_status = finding.status
    finding.status = body.status
    await db.flush()
    if old_status != body.status:
        activity = ActivityLogModel(
            case_id=finding.case_id,
            event_type="finding_status_updated",
            payload={
                "finding_id": str(finding_id),
                "old_status": old_status,
                "new_status": body.status,
            },
        )
        db.add(activity)
    await db.refresh(finding)
    return FindingResponse(**orm_to_finding_response(finding))
