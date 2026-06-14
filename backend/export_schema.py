"""Export the FastAPI OpenAPI schema to stdout without starting the server.

Usage (from project root):
    cd backend && python export_schema.py > ../openapi.json

Requires only APP_ENVIRONMENT and a syntactically valid DATABASE_URL;
no running database, Redis, or MinIO connection is needed.
"""

import json
import os
import sys

# Minimum env vars required by Settings() — no real connections are made.
os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db"
)
os.environ.setdefault("DEBUG", "true")

sys.path.insert(0, os.path.dirname(__file__))

from app.main import app  # noqa: E402

json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2)
sys.stdout.write("\n")
