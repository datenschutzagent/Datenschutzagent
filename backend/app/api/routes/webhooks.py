"""Webhook-Management API: Konfiguration ausgehender HTTP-Benachrichtigungen."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import WebhookConfigModel, WebhookDeliveryLogModel

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_EVENTS = {
    "case_status_changed",
    "finding_created",
    "finding_status_changed",
    "data_breach_created",
    "dsr_created",
    "avv_expiry_warning",
}


class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str | None = None
    events: list[str] = []  # leer = alle Events


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    id: UUID
    name: str
    url: str
    has_secret: bool
    events: list[str]
    is_active: bool
    created_by: str


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    webhook_id: UUID
    event_type: str
    status: str
    http_status: int | None
    error: str | None
    attempts: int
    delivered_at: str | None


def _orm_to_response(w: WebhookConfigModel) -> WebhookResponse:
    return WebhookResponse(
        id=w.id,
        name=w.name,
        url=w.url,
        has_secret=bool(w.secret),
        events=w.events or [],
        is_active=w.is_active,
        created_by=w.created_by,
    )


def _delivery_to_response(d: WebhookDeliveryLogModel) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse(
        id=d.id,
        webhook_id=d.webhook_id,
        event_type=d.event_type,
        status=d.status,
        http_status=d.http_status,
        error=d.error,
        attempts=d.attempts,
        delivered_at=d.delivered_at.isoformat() if d.delivered_at else None,
    )


@router.get("", summary="Webhooks auflisten")
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
) -> list[WebhookResponse]:
    result = await db.execute(select(WebhookConfigModel).order_by(WebhookConfigModel.created_at.desc()))
    return [_orm_to_response(w) for w in result.scalars().all()]


@router.post("", status_code=201, summary="Webhook anlegen")
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
) -> WebhookResponse:
    invalid = [e for e in body.events if e not in VALID_EVENTS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unbekannte Events: {invalid}. Erlaubt: {sorted(VALID_EVENTS)}")
    creator = getattr(_user, "display_name", "") if _user else ""
    webhook = WebhookConfigModel(
        name=body.name,
        url=body.url,
        secret=body.secret,
        events=body.events,
        created_by=creator,
    )
    db.add(webhook)
    await db.flush()
    await db.refresh(webhook)
    return _orm_to_response(webhook)


@router.patch("/{webhook_id}", summary="Webhook aktualisieren")
async def update_webhook(
    webhook_id: UUID,
    body: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
) -> WebhookResponse:
    result = await db.execute(select(WebhookConfigModel).where(WebhookConfigModel.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    if body.events is not None:
        invalid = [e for e in body.events if e not in VALID_EVENTS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Unbekannte Events: {invalid}")
    for field in ["name", "url", "secret", "events", "is_active"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(webhook, field, val)
    await db.flush()
    await db.refresh(webhook)
    return _orm_to_response(webhook)


@router.delete("/{webhook_id}", status_code=204, summary="Webhook löschen")
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(select(WebhookConfigModel).where(WebhookConfigModel.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    await db.delete(webhook)
    await db.flush()


@router.post("/{webhook_id}/test", summary="Webhook testen")
async def test_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Sendet ein Test-Event an den konfigurierten Webhook-Endpunkt."""
    result = await db.execute(select(WebhookConfigModel).where(WebhookConfigModel.id == webhook_id))
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    from app.services.webhook_service import _deliver_webhook
    success, http_status, error = await _deliver_webhook(
        webhook.id,
        webhook.url,
        webhook.secret,
        "test",
        {"message": "Datenschutzagent Test-Event", "webhook_id": str(webhook.id)},
    )
    return {"success": success, "http_status": http_status, "error": error}


@router.get("/{webhook_id}/deliveries", summary="Webhook-Zustellprotokolle abrufen")
async def get_webhook_deliveries(
    webhook_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
) -> list[WebhookDeliveryResponse]:
    result = await db.execute(
        select(WebhookDeliveryLogModel)
        .where(WebhookDeliveryLogModel.webhook_id == webhook_id)
        .order_by(WebhookDeliveryLogModel.created_at.desc())
        .limit(limit)
    )
    return [_delivery_to_response(d) for d in result.scalars().all()]


@router.get("/events", summary="Verfügbare Webhook-Events auflisten")
def list_webhook_events(_user=require_roles("admin")) -> list[str]:
    return sorted(VALID_EVENTS)
