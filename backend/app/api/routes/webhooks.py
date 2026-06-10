"""Webhook-Management API: Konfiguration ausgehender HTTP-Benachrichtigungen."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.rate_limit import limiter
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


def _validate_webhook_url(url: str) -> str:
    """Validate webhook URL to prevent SSRF attacks.

    Blocks requests to private/loopback/link-local addresses to prevent
    Server-Side Request Forgery (SSRF) attacks (OWASP A10).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Webhook URL must use http or https scheme")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Webhook URL must have a valid hostname")
    # Try to resolve hostname and check if it points to a private/internal address
    try:
        resolved_ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(resolved_ip)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
        ):
            logger.warning(
                "SSRF attempt blocked: webhook URL resolves to internal address",
                extra={
                    "event": "ssrf_blocked",
                    "hostname": hostname,
                    "resolved_ip": resolved_ip,
                },
            )
            raise ValueError(
                f"Webhook URL must not point to private or internal addresses (resolved: {resolved_ip})"
            )
    except socket.gaierror:
        # DNS resolution may fail at validation time; will fail at delivery time
        pass
    return url


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., max_length=2000)
    secret: str | None = Field(default=None, max_length=500)
    events: list[str] = []  # leer = alle Events

    @field_validator("url")
    @classmethod
    def validate_url_no_ssrf(cls, v: str) -> str:
        return _validate_webhook_url(v)


class WebhookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    secret: str | None = Field(default=None, max_length=500)
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url_no_ssrf(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_webhook_url(v)
        return v


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
    result = await db.execute(
        select(WebhookConfigModel).order_by(WebhookConfigModel.created_at.desc())
    )
    return [_orm_to_response(w) for w in result.scalars().all()]


@router.post("", status_code=201, summary="Webhook anlegen")
@limiter.limit("20/minute")
async def create_webhook(
    request: Request,
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
) -> WebhookResponse:
    invalid = [e for e in body.events if e not in VALID_EVENTS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannte Events: {invalid}. Erlaubt: {sorted(VALID_EVENTS)}",
        )
    creator = getattr(_user, "display_name", "") if _user else ""
    webhook = WebhookConfigModel(
        name=body.name,
        url=body.url,
        secret=encrypt_secret(body.secret) if body.secret else None,
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
    result = await db.execute(
        select(WebhookConfigModel).where(WebhookConfigModel.id == webhook_id)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    if body.events is not None:
        invalid = [e for e in body.events if e not in VALID_EVENTS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Unbekannte Events: {invalid}")
    for field in ["name", "url", "events", "is_active"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(webhook, field, val)
    if body.secret is not None:
        webhook.secret = encrypt_secret(body.secret) if body.secret else None
    await db.flush()
    await db.refresh(webhook)
    return _orm_to_response(webhook)


@router.delete("/{webhook_id}", status_code=204, summary="Webhook löschen")
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(
        select(WebhookConfigModel).where(WebhookConfigModel.id == webhook_id)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    await db.delete(webhook)
    await db.flush()


@router.post("/{webhook_id}/test", summary="Webhook testen")
@limiter.limit("5/minute")
async def test_webhook(
    request: Request,
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Sendet ein Test-Event an den konfigurierten Webhook-Endpunkt."""
    result = await db.execute(
        select(WebhookConfigModel).where(WebhookConfigModel.id == webhook_id)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook nicht gefunden")
    from app.services.webhook_service import _deliver_webhook

    success, http_status, error = await _deliver_webhook(
        webhook.id,
        webhook.url,
        decrypt_secret(webhook.secret) if webhook.secret else None,
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
