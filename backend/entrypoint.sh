#!/bin/sh
# Container entrypoint: run Alembic migrations then start uvicorn.
# Use 'sh' (not 'bash') for Alpine/slim images.
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
