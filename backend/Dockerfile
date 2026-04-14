# Datenschutzagent Backend
FROM python:3.12-slim

WORKDIR /app

# System deps for building wheels (libpq-dev for psycopg2; build-essential only at build time)
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Run with uvicorn; host 0.0.0.0 for Docker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
