# CLAUDE.md – Datenschutzagent

This file provides AI assistants with the context needed to understand, develop, and maintain this codebase effectively.

---

## Project Overview

**Datenschutzagent** is a full-stack web application that helps university data protection officers manage research project compliance reviews. It provides:

- Case management for data protection reviews
- Document upload, text extraction (PDF/DOCX/XLSX), and OCR for scanned PDFs
- Playbook-driven LLM compliance checks via Ollama
- Findings and risk assessment tracking
- VVT (Verfahrensverzeichnis) data normalization
- DSB (Datenschutzbeauftragter) report generation
- RAG-based legal reference lookup via Weaviate
- OIDC/OAuth2 authentication with RBAC

The application is **German-first**: UI, documentation, and domain terminology are in German.

---

## Repository Structure

```
Datenschutzagent/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point, lifespan hooks
│   │   ├── config.py           # Pydantic Settings (env-driven)
│   │   ├── database.py         # SQLAlchemy async DB setup
│   │   ├── storage.py          # MinIO/S3 + local storage abstraction
│   │   ├── cli.py              # CLI for user/role/config management
│   │   ├── celery_app.py       # Celery task queue setup
│   │   ├── api/
│   │   │   └── routes/         # FastAPI route handlers
│   │   │       ├── cases.py
│   │   │       ├── documents.py
│   │   │       ├── findings.py
│   │   │       ├── playbooks.py
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── departments.py
│   │   │       ├── legal_bases.py
│   │   │       ├── vvt_overview.py
│   │   │       ├── admin.py
│   │   │       └── admin_prompt_templates.py
│   │   ├── models/
│   │   │   ├── db.py           # SQLAlchemy ORM models
│   │   │   └── schemas.py      # Pydantic request/response schemas
│   │   ├── services/           # Business logic (service layer)
│   │   │   ├── document_processor.py
│   │   │   ├── run_checks_service.py
│   │   │   ├── check_runner.py
│   │   │   ├── dsb_report_service.py
│   │   │   ├── vvt_service.py
│   │   │   ├── playbook_import.py
│   │   │   ├── weaviate_service.py
│   │   │   ├── annotated_document_service.py
│   │   │   ├── prompt_template_service.py
│   │   │   └── connection_checks.py
│   │   ├── core/
│   │   │   ├── auth.py         # OIDC/JWT authentication logic
│   │   │   └── llm.py          # LLM integration (Ollama via pydantic-ai)
│   │   └── data/
│   │       ├── fachbereiche.yaml  # Department definitions (seed data)
│   │       └── playbooks/         # YAML playbooks per department (seed data)
│   ├── migrations/             # SQL migration files (001–011)
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_api.py
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── src/                        # React TypeScript frontend
│   └── app/
│       ├── App.tsx
│       ├── main.tsx            # React entry point
│       ├── routes.tsx          # React Router v7 configuration
│       ├── pages/              # Full-page route components
│       ├── components/         # Reusable UI components
│       │   ├── case-detail/
│       │   └── ui/             # Radix UI primitives
│       ├── contexts/
│       │   ├── AuthContext.tsx
│       │   └── PreferencesContext.tsx
│       └── lib/
├── mkdocs/                     # MkDocs documentation site
│   ├── docs/                   # Markdown source files
│   └── mkdocs.yml
├── .github/
│   └── workflows/
│       └── test.yml            # CI: frontend (Vitest) + backend (pytest)
├── docker-compose.yml          # Full stack: postgres, redis, minio, weaviate, backend, worker, frontend
├── Dockerfile.frontend         # Multi-stage: Node 20 build → Nginx alpine
├── package.json                # Frontend deps (npm)
├── vite.config.ts              # Vite + Vitest config
├── index.html                  # SPA shell
├── .env.example                # All configurable env vars with comments
└── README.md                   # German overview and quick-start
```

---

## Technology Stack

### Backend
| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 (async) |
| Language | Python 3.12 |
| Database | PostgreSQL 16, SQLAlchemy 2.0 async, asyncpg |
| Migrations | Manual SQL files in `backend/migrations/` |
| Task Queue | Celery 5.4 + Redis 7 |
| Storage | MinIO (S3-compatible) or local filesystem |
| LLM | Ollama (local) via `pydantic-ai` + OpenAI-compatible API |
| Vector DB | Weaviate 1.27 (optional RAG) |
| Auth | PyJWT, OIDC/OAuth2 |
| Validation | Pydantic 2.10 |
| Testing | pytest 8.3 + pytest-asyncio 0.24 |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18.3 + TypeScript |
| Build tool | Vite 6.3 |
| Styling | Tailwind CSS 4.1 |
| UI components | Radix UI (unstyled primitives) + MUI icons |
| Routing | React Router v7 |
| Forms | React Hook Form 7.55 |
| Charts | Recharts 2.15 |
| Markdown | react-markdown + @uiw/react-md-editor |
| Testing | Vitest 4.0 + @testing-library/react |

### Infrastructure
- Docker Compose orchestrates all services locally
- GitHub Actions for CI/CD (runs on push/PR to `main`/`master`)

---

## Development Setup

### Prerequisites
- Docker and Docker Compose
- Ollama running externally (see `OLLAMA_BASE_URL`)
- Node 20 and npm (for frontend-only work)
- Python 3.12 (for backend-only work)

### Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env as needed (Ollama URL, optional OIDC, storage, etc.)

# 2. Start all services
docker compose up -d

# 3. Access the application
# Frontend:   http://localhost:3002
# Backend:    http://localhost:8002
# API docs:   http://localhost:8002/docs
# MinIO UI:   http://localhost:9001 (minioadmin/minioadmin)
```

### Frontend Development (without Docker)

```bash
npm install
npm run dev       # Vite dev server on http://localhost:3002
npm run build     # Production build to dist/
npm run test      # Run Vitest once
npm run test:watch  # Vitest in watch mode
```

### Backend Development (without Docker)

```bash
cd backend
pip install -r requirements.txt

# Requires a running PostgreSQL
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/datenschutzagent
export OLLAMA_ENABLED=false

uvicorn app.main:app --reload --port 8000

# Run tests
python -m pytest tests/ -v
```

### MkDocs Documentation

```bash
pip install mkdocs mkdocs-material
mkdocs serve -f mkdocs/mkdocs.yml   # Served at http://localhost:8000
mkdocs build -f mkdocs/mkdocs.yml   # Outputs to mkdocs/site/
```

---

## Key Conventions

### Backend Conventions

1. **Service layer**: Business logic lives in `app/services/`. Route handlers in `app/api/routes/` should only handle HTTP concerns and delegate to services.

2. **Async everywhere**: All database operations use SQLAlchemy async sessions. Use `async_session_factory` for context managers outside request scope.

3. **Pydantic for I/O**: Define request/response schemas in `app/models/schemas.py`. ORM models in `app/models/db.py` are SQLAlchemy only — never expose ORM models directly via the API.

4. **Configuration**: All settings come from environment variables via `app/config.py` (Pydantic Settings). Never hard-code URLs, credentials, or feature flags.

5. **Database migrations**: Add new `.sql` files to `backend/migrations/` with the next sequential number (e.g., `012_add_new_table.sql`). Migrations are applied manually or on startup.

6. **Authentication**:
   - When `OIDC_ENABLED=false` (default), a default user (`00000000-0000-4000-8000-000000000001`) is used automatically.
   - When `OIDC_ENABLED=true`, routes protected via `app/core/auth.py` require a valid JWT Bearer token.
   - RBAC roles: `viewer`, `editor`, `admin`. Default for new OIDC users is `RBAC_DEFAULT_ROLE`.

7. **LLM integration**: All LLM calls go through `app/core/llm.py` and `pydantic-ai`. The model is configured via `OLLAMA_MODEL`. When `OLLAMA_ENABLED=false`, LLM-dependent features degrade gracefully.

8. **Celery tasks**: CPU-heavy work (document text extraction) runs as Celery tasks when `CELERY_ENABLED=true`. When disabled, extraction runs synchronously at upload time.

9. **Storage abstraction**: Use `app/storage.py` for all file I/O. Supports `local` (default) or `minio` backends controlled by `STORAGE_BACKEND`.

10. **Playbooks**: Compliance check playbooks are defined as YAML files in `backend/app/data/playbooks/` and imported into the database at startup via `app/services/playbook_import.py`. New playbooks must follow the existing YAML schema.

### Frontend Conventions

1. **Component organization**: Place page-level components in `src/app/pages/`. Reusable components go in `src/app/components/`. Radix UI wrappers go in `src/app/components/ui/`.

2. **Routing**: Use React Router v7 with the configuration in `src/app/routes.tsx`. Protected routes are wrapped with `AuthGuard`.

3. **Global state**: Use `AuthContext` for authentication state and `PreferencesContext` for user preferences (theme, language). Avoid prop-drilling; reach for context when data is needed across many components.

4. **API calls**: Use the native `fetch` API (no axios/tanstack-query). The base API URL comes from the `VITE_API_URL` env var at build time.

5. **Styling**: Use Tailwind CSS utility classes. For dynamic class merging, use `clsx` + `tailwind-merge`. Follow the existing component styling patterns.

6. **Forms**: Use React Hook Form for any form with validation logic.

7. **Markdown**: Use `@uiw/react-md-editor` for editing and `react-markdown` for display.

8. **Imports**: Use the `@` path alias for imports from `src/` (e.g., `import Foo from '@/components/Foo'`).

---

## API Reference

- **Base URL**: `http://localhost:8002/api/v1`
- **Interactive docs**: `http://localhost:8002/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8002/redoc`
- **Health check**: `GET /health` — returns `{"status": "ok"}` or `{"status": "degraded", "ollama": "unreachable"}`

### Key Route Groups
| Prefix | Module |
|---|---|
| `/api/v1/cases` | Cases CRUD |
| `/api/v1/documents` | Document upload/extraction |
| `/api/v1/findings` | Findings management |
| `/api/v1/playbooks` | Playbook management |
| `/api/v1/auth` | OIDC config (public) |
| `/api/v1/users` | User management |
| `/api/v1/departments` | Department data |
| `/api/v1/legal-bases` | Legal bases + RAG |
| `/api/v1/vvt-overview` | VVT normalization |
| `/api/v1/admin` | Admin settings |
| `/api/v1/admin/prompt-templates` | Versioned LLM prompts |

---

## Database Models

Key ORM models in `backend/app/models/db.py`:

| Model | Purpose |
|---|---|
| `CaseModel` | A data protection review case |
| `DocumentModel` | Uploaded document with extraction status |
| `DocumentCommentModel` | Threaded comments on documents |
| `FindingModel` | A compliance finding/issue in a case |
| `PlaybookModel` | LLM-driven check definition |
| `LegalBaseModel` | Legal reference (indexed in Weaviate) |
| `UserModel` | User account with OIDC info and preferences |
| `RunCheckJobModel` | Async compliance check job tracking |
| `DsbReportModel` | Generated DSB report |
| `PromptTemplateModel` | Versioned LLM prompt templates |

---

## CLI Commands

The backend ships a CLI for administrative tasks:

```bash
cd backend

# List all users
python -m app.cli users list

# Change a user's role
python -m app.cli users set-role <user-uuid> <viewer|editor|admin>

# Show the default user
python -m app.cli users show-default

# Show effective config
python -m app.cli config show

# Check service connections (DB, Ollama, Redis, Weaviate)
python -m app.cli config check
```

---

## Environment Variables

All variables are documented in `.env.example`. Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | (required) | PostgreSQL async connection string |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | LLM model name |
| `OLLAMA_ENABLED` | `true` | Enable/disable LLM features |
| `OLLAMA_OCR_ENABLED` | `false` | OCR for scanned PDFs |
| `OLLAMA_OCR_MODEL` | — | Vision model for OCR (e.g., `qwen2.5-vl`) |
| `CORS_ORIGINS` | — | Comma-separated allowed frontend origins |
| `VITE_API_URL` | — | Backend URL used by the browser (build-time) |
| `CELERY_ENABLED` | `false` | Async document extraction |
| `CELERY_BROKER_URL` | — | Redis URL for Celery |
| `WEAVIATE_URL` | — | Weaviate URL for RAG |
| `WEAVIATE_INDEXING_ENABLED` | `false` | Enable RAG indexing |
| `OIDC_ENABLED` | `false` | Enable OIDC authentication |
| `OIDC_ISSUER_URL` | — | OIDC provider URL |
| `RBAC_DEFAULT_ROLE` | `viewer` | Role assigned to new OIDC users |
| `STORAGE_BACKEND` | `local` | `local` or `minio` |
| `CURRENT_USER_ID` | `00000000-0000-4000-8000-000000000001` | Default user (no OIDC) |

---

## Testing

### Frontend

```bash
npm run test          # Run all tests once (Vitest)
npm run test:watch    # Watch mode
```

Tests use jsdom environment. Test files match `src/**/*.{test,spec}.{ts,tsx}`.

### Backend

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/datenschutzagent_test \
OLLAMA_ENABLED=false \
python -m pytest tests/ -v
```

Tests are async (`pytest-asyncio` with `asyncio_mode = auto` in `pytest.ini`). The CI pipeline spins up a fresh PostgreSQL 16 container for each run.

### CI/CD

GitHub Actions workflow at `.github/workflows/test.yml` runs on push/PR to `main`/`master`:

- **Frontend job**: `npm ci` → `npm run test`
- **Backend job**: Python 3.12, PostgreSQL 16-alpine → `pip install` → `pytest`

---

## Docker Compose Services

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | postgres:16 | 5432 | Primary database |
| `redis` | redis:7 | 6379 | Celery broker |
| `minio` | minio/minio | 9000/9001 | S3-compatible storage |
| `weaviate` | semitechnologies/weaviate:1.27 | 8080 | Vector DB for RAG |
| `backend` | custom (Dockerfile) | 8002 | FastAPI application |
| `worker` | custom (Dockerfile) | — | Celery worker |
| `frontend` | custom (Dockerfile.frontend) | 3002 | Nginx serving React SPA |

All services include health checks. Data is persisted via named Docker volumes.

---

## Common Development Tasks

### Add a new API endpoint
1. Add a route handler to the appropriate file in `backend/app/api/routes/` (or create a new one)
2. Add request/response schemas to `backend/app/models/schemas.py`
3. Implement business logic in a service in `backend/app/services/`
4. Register the router in `backend/app/api/__init__.py`

### Add a new database table
1. Add an ORM model to `backend/app/models/db.py`
2. Create a new migration SQL file: `backend/migrations/0XX_add_<table_name>.sql`
3. Add corresponding Pydantic schemas to `backend/app/models/schemas.py`

### Add a new frontend page
1. Create a page component in `src/app/pages/`
2. Add a route to `src/app/routes.tsx`
3. Add navigation link if needed in the sidebar/nav components

### Update a playbook
- Edit or add YAML files in `backend/app/data/playbooks/`
- Playbooks are re-imported on backend startup (only new entries are added)

### Add a new environment variable
1. Add it to `.env.example` with a descriptive comment
2. Add it to `backend/app/config.py` as a Pydantic Settings field

---

## Notes for AI Assistants

- **Language**: All user-facing strings, variable names for domain concepts, and documentation are in German. Comments in Python/TypeScript code may be in English or German.
- **Async**: The backend is fully async. Always use `await` for database operations and avoid blocking I/O in route handlers.
- **Optional features**: Ollama, Celery, Weaviate, and OIDC are all optional. Code that depends on them must respect their enabled/disabled state.
- **No direct DB exposure**: Never return SQLAlchemy model instances from API routes. Always convert to Pydantic schemas first.
- **httpx pinning**: `httpx` is pinned to `>=0.27.0,<0.28.0` due to `ollama==0.4.1` compatibility. Do not upgrade httpx without verifying ollama compatibility.
- **React/Vite**: The frontend uses `peerDependencies` for react/react-dom. These must be installed separately (they are typically provided by the environment). In practice, use `npm install` which handles all deps.
- **Migration numbering**: SQL migration files use zero-padded sequential numbering (e.g., `012_...`). Do not skip numbers or reorder existing files.
