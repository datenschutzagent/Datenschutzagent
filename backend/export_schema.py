"""Export the FastAPI OpenAPI schema to stdout without starting the server.

Usage (from project root):
    cd backend && python export_schema.py > ../openapi.json

Requires only APP_ENVIRONMENT and a syntactically valid DATABASE_URL;
no running database, Redis, or MinIO connection is needed.
"""

import contextlib
import json
import os
import sys

# Minimum env vars required by Settings() — no real connections are made.
os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost:5432/db",  # pragma: allowlist secret
)
os.environ.setdefault("DEBUG", "true")

sys.path.insert(0, os.path.dirname(__file__))

# Importing the app pulls in third-party modules that print to stdout on import
# (PyMuPDF's "fitz API is deprecated" notice). stdout must carry nothing but the
# schema — the CI drift check diffs it byte for byte — so those go to stderr.
with contextlib.redirect_stdout(sys.stderr):
    from app.main import app  # noqa: E402

json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2)
sys.stdout.write("\n")
