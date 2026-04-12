"""Webhook-Service: Sendet ausgehende HTTP-Benachrichtigungen bei Events.

Unterstützte Events:
  - case_status_changed
  - finding_created
  - finding_status_changed
  - data_breach_created
  - dsr_created

Jeder Webhook-Aufruf wird im WebhookDeliveryLogModel protokolliert.
HMAC-SHA256-Signatur im Header X-Datenschutzagent-Signature wenn secret konfiguriert.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.core.crypto import decrypt_secret

logger = logging.getLogger(__name__)


def _sign_payload(secret: str, payload_bytes: bytes) -> str:
    """Erstellt HMAC-SHA256-Signatur für den Payload."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


async def _deliver_webhook(
    webhook_id: UUID,
    url: str,
    secret: str | None,
    event_type: str,
    payload: dict[str, Any],
) -> tuple[bool, int | None, str | None]:
    """Sendet einen einzelnen Webhook-Request. Gibt (success, http_status, error) zurück."""
    payload_bytes = json.dumps(payload, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Datenschutzagent-Event": event_type,
        "User-Agent": "Datenschutzagent-Webhook/1.0",
    }
    if secret:
        headers["X-Datenschutzagent-Signature"] = _sign_payload(secret, payload_bytes)

    timeout = settings.webhook_timeout_seconds
    last_error = None
    for attempt in range(settings.webhook_max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, content=payload_bytes, headers=headers)
                if response.is_success:
                    return True, response.status_code, None
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Webhook delivery attempt %d/%d failed for %s: %s",
                attempt + 1, settings.webhook_max_retries, url, last_error
            )

    return False, None, last_error


async def fire_event(event_type: str, payload: dict[str, Any], db) -> int:
    """Feuert ein Event an alle passenden aktiven Webhooks.

    Args:
        event_type: Name des Events (z.B. "case_status_changed")
        payload: Event-Daten (werden als JSON gesendet)
        db: AsyncSession

    Returns:
        Anzahl erfolgreich zugestellter Webhooks
    """
    from sqlalchemy import select, and_
    from app.models.db import WebhookConfigModel, WebhookDeliveryLogModel

    result = await db.execute(
        select(WebhookConfigModel).where(
            WebhookConfigModel.is_active == True,  # noqa: E712
        )
    )
    webhooks = result.scalars().all()
    # Nur Webhooks, die dieses Event abonniert haben
    matching = [w for w in webhooks if not w.events or event_type in w.events]

    if not matching:
        return 0

    full_payload = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }

    success_count = 0
    for webhook in matching:
        raw_secret = decrypt_secret(webhook.secret) if webhook.secret else None
        success, http_status, error = await _deliver_webhook(
            webhook.id, webhook.url, raw_secret, event_type, full_payload
        )
        log_entry = WebhookDeliveryLogModel(
            webhook_id=webhook.id,
            event_type=event_type,
            payload=full_payload,
            status="success" if success else "failed",
            http_status=http_status,
            error=error,
            attempts=settings.webhook_max_retries if not success else 1,
            delivered_at=datetime.now(timezone.utc) if success else None,
        )
        db.add(log_entry)
        if success:
            success_count += 1

    await db.flush()
    return success_count
