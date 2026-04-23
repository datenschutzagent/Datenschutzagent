"""Shared rate limiter instance for use across route modules.

The default slowapi ``get_remote_address`` trusts any client-supplied
``X-Forwarded-For`` header, which lets attackers bypass rate limits by forging
the header. Our ``_trusted_forwarded_for`` only honours the header when the
direct socket peer is listed in the ``trusted_proxies`` setting (exact IPs or
CIDR ranges).
"""
from __future__ import annotations

import ipaddress
import logging

from slowapi import Limiter
from starlette.requests import Request

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_trusted_networks() -> list[ipaddress._BaseNetwork]:
    networks: list[ipaddress._BaseNetwork] = []
    for entry in settings.trusted_proxies if isinstance(settings.trusted_proxies, list) else []:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            # Validated in config.py; defensive fallback keeps the limiter functional.
            logger.warning("Ignoring invalid trusted_proxies entry: %r", entry)
    return networks


_TRUSTED_NETWORKS = _parse_trusted_networks()


def _trusted_forwarded_for(request: Request) -> str:
    """Return the client IP for rate-limiting.

    Rules:
    - If the direct peer (``request.client.host``) is listed in
      ``trusted_proxies``, honour the first (left-most) entry of
      ``X-Forwarded-For`` — that is the original client as seen by the trusted
      proxy.
    - Otherwise, use the direct peer address. This prevents header forgery
      when the app is exposed directly or when an attacker can reach it
      without traversing the configured proxy.
    """
    peer = (request.client.host if request.client else "") or "unknown"
    if not _TRUSTED_NETWORKS:
        return peer
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_addr in net for net in _TRUSTED_NETWORKS):
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    if not forwarded:
        return peer
    first_hop = forwarded.split(",", 1)[0].strip()
    try:
        ipaddress.ip_address(first_hop)
    except ValueError:
        return peer
    return first_hop


limiter = Limiter(key_func=_trusted_forwarded_for)
