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
import asyncio
import hashlib
import hmac
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.core.crypto import decrypt_secret

logger = logging.getLogger(__name__)

# HTTP-Statuscodes, die trotz 4xx einen Retry rechtfertigen (Rate-Limit / Timeout).
_RETRIABLE_4XX = {408, 425, 429}


def _sign_payload(secret: str, payload_bytes: bytes) -> str:
    """Erstellt HMAC-SHA256-Signatur für den Payload."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def _backoff_delay(attempt_index: int) -> float:
    """Berechnet Wartezeit vor Retry `attempt_index` (0-basiert nach erstem Fehler).

    Exponentielles Backoff mit optionalem Jitter. Beispiel (base=2, max=30, jitter=0.25):
      attempt_index=0 → ~2s ± 25%
      attempt_index=1 → ~4s ± 25%
      attempt_index=2 → ~8s ± 25%
      attempt_index=3 → ~16s ± 25%
      attempt_index=4 → 30s (capped)
    """
    base = max(0.0, float(settings.webhook_backoff_base_seconds))
    max_delay = max(base, float(settings.webhook_backoff_max_seconds))
    jitter = max(0.0, min(1.0, float(settings.webhook_backoff_jitter)))
    raw = base * (2 ** attempt_index)
    delay = min(raw, max_delay)
    if jitter > 0:
        spread = delay * jitter
        delay += random.uniform(-spread, spread)
    return max(0.0, delay)


def _is_retriable_status(status_code: int) -> bool:
    """True für 5xx und bekannte „retry-bar" 4xx (408 Request Timeout, 429 Too Many Requests)."""
    if status_code >= 500:
        return True
    return status_code in _RETRIABLE_4XX


async def _deliver_webhook(
    webhook_id: UUID,
    url: str,
    secret: str | None,
    event_type: str,
    payload: dict[str, Any],
) -> tuple[bool, int | None, str | None, int]:
    """Sendet einen einzelnen Webhook-Request. Gibt (success, http_status, error, attempts) zurück.

    Retry-Strategie:
      - Netzwerkfehler / Timeouts: retry bis max_retries erreicht.
      - 5xx-Antworten: retry bis max_retries erreicht.
      - 408/425/429: retry (Server signalisiert temporäres Problem).
      - Andere 4xx: sofort abbrechen (fehlerhafter Request, Retry sinnlos).
    """
    payload_bytes = json.dumps(payload, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Datenschutzagent-Event": event_type,
        "User-Agent": "Datenschutzagent-Webhook/1.0",
    }
    if secret:
        headers["X-Datenschutzagent-Signature"] = _sign_payload(secret, payload_bytes)

    timeout = settings.webhook_timeout_seconds
    max_retries = max(1, int(settings.webhook_max_retries))

    last_error: str | None = None
    last_status: int | None = None
    attempts = 0
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            attempts = attempt + 1
            if attempt > 0:
                await asyncio.sleep(_backoff_delay(attempt - 1))
            try:
                response = await client.post(url, content=payload_bytes, headers=headers)
                last_status = response.status_code
                if response.is_success:
                    return True, response.status_code, None, attempts
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                if not _is_retriable_status(response.status_code):
                    logger.warning(
                        "Webhook delivery gave non-retriable status %d for %s; giving up after %d attempt(s)",
                        response.status_code, url, attempts,
                    )
                    return False, response.status_code, last_error, attempts
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                last_status = None
            except Exception as exc:
                last_error = str(exc)
                last_status = None
            logger.warning(
                "Webhook delivery attempt %d/%d failed for %s: %s",
                attempts, max_retries, url, last_error,
            )

    return False, last_status, last_error, attempts


async def fire_event(event_type: str, payload: dict[str, Any], db) -> int:
    """Feuert ein Event an alle passenden aktiven Webhooks.

    Args:
        event_type: Name des Events (z.B. "case_status_changed")
        payload: Event-Daten (werden als JSON gesendet)
        db: AsyncSession

    Returns:
        Anzahl erfolgreich zugestellter Webhooks
    """
    from sqlalchemy import select
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
        success, http_status, error, attempts = await _deliver_webhook(
            webhook.id, webhook.url, raw_secret, event_type, full_payload
        )
        log_entry = WebhookDeliveryLogModel(
            webhook_id=webhook.id,
            event_type=event_type,
            payload=full_payload,
            status="success" if success else "failed",
            http_status=http_status,
            error=error,
            attempts=attempts,
            delivered_at=datetime.now(timezone.utc) if success else None,
        )
        db.add(log_entry)
        if success:
            success_count += 1

    await db.flush()
    return success_count
