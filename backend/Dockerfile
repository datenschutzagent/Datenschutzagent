# Datenschutzagent Backend
FROM python:3.12-slim

WORKDIR /app

# System deps for building wheels (libpq-dev for psycopg2; build-essential only at build time).
# The dist-upgrade pulls Debian security fixes the base image does not ship yet
# (e.g. openssl CVE-2026-45447 fixed in 3.5.6-1~deb13u2) — the Trivy gate fails on
# fixable HIGH/CRITICAL CVEs, so the image must be patched at build time.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove build tools to reduce attack surface (libpq-dev runtime still needed)
RUN apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Run as non-root user for security (prevents privilege escalation on container escape)
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appgroup /app

USER appuser

# Run Alembic migrations then start uvicorn (see entrypoint.sh)
CMD ["./entrypoint.sh"]
