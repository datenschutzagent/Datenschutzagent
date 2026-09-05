#!/bin/sh
# Container entrypoint: run Alembic migrations then start uvicorn.
# Use 'sh' (not 'bash') for Alpine/slim images.
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

# Reverse-proxy awareness: honour X-Forwarded-For / X-Forwarded-Proto only from the
# proxies listed in TRUSTED_PROXIES (same list the rate limiter trusts; IPs or CIDR).
# Without it request.url.scheme stays "http" behind a TLS-terminating proxy and
# request.client.host is the proxy address. Empty TRUSTED_PROXIES → uvicorn's
# default (loopback only), i.e. forwarded headers from the network are ignored.
FORWARDED_ALLOW_IPS="${TRUSTED_PROXIES:-127.0.0.1}"

echo "[entrypoint] Starting uvicorn (forwarded-allow-ips=${FORWARDED_ALLOW_IPS})..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS}"
