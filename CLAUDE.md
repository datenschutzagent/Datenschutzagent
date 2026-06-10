# CLAUDE.md

Kurzreferenz für KI-Agenten (und neue Entwickler:innen), die in diesem Repo arbeiten.

## Was ist das?

**DatenschutzAgent** — DSGVO-Compliance-Tool: Vorgänge (Cases) verwalten,
Dokumente hochladen, LLM-gestützte Playbook-Checks ausführen, Findings, DSB-Reports,
VVT-Normalisierung (Art. 30), DSFA, AVV-Risiko u. v. m. Konfigurierbar über
Org-Profile (YAML) ohne Code-Änderungen.

## Architektur (grob)

- **Backend** (`backend/`): FastAPI + SQLAlchemy (async) + PostgreSQL; Celery + Redis
  für asynchrone Extraktion; MinIO (S3) für Dateien; Weaviate (optional) für RAG;
  LLM via Pydantic-AI (Ollama/OpenAI/Anthropic, pluggable).
  - `app/api/routes/` — REST-Endpunkte (~160). `app/services/` — Business-Logik.
    `app/models/_db/` — ORM, `app/models/_schemas/` — Pydantic. `app/core/` — Auth,
    Rate-Limit, Crypto, LLM, Request-ID. `app/data/` — Playbooks/Org-Profile (YAML).
  - Einstieg: `app/main.py` (konfiguriert Logging **vor** App-Imports — daher die
    bewussten `# noqa: E402` dort; nicht „aufräumen").
- **Frontend** (`src/app/`): React 18 + Vite + Tailwind + Radix UI; TanStack Query;
  API-Typen aus OpenAPI generiert (`npm run generate:api`). Striktes TypeScript.
- **Doku**: `mkdocs/` (Material). Roadmap/Sprints unter `mkdocs/docs/projekt/`.

## Befehle

```bash
# Stack starten
cp .env.example .env && docker compose up -d   # FE:3002  BE:8002

# Backend (in backend/)
ruff check .            # Lint  (Config: ruff.toml)
black --check .         # Format (Default 88; wie im Pre-Commit)
pytest tests/ -v        # Tests — braucht DATABASE_URL=postgresql+asyncpg://...
python -m evals.run     # Offline-Qualitäts-Gate
alembic upgrade head    # Migrationen anwenden

# Frontend (Projektwurzel)
npm run lint            # ESLint
npm run typecheck       # tsc --noEmit
npm run test            # Vitest
npm run test:e2e        # Playwright (Stack muss laufen)
```

## Konventionen & Fallstricke

- **Migrationen: nur Alembic** (`backend/alembic/`). Rohe SQL-Dateien unter
  `backend/migrations/legacy/` sind historisch (vor Baseline) und inaktiv.
- **Lint/Format werden in CI erzwungen** (`.github/workflows/test.yml`). Vor dem
  Pushen lokal `ruff check . && black --check .` (Backend) laufen lassen.
- Broad `except Exception` ist nur in definierten Infra-/Route-Dateien erlaubt
  (per-file-ignores in `ruff.toml`, Regel BLE001) — anderswo spezifische Exceptions.
- SQLAlchemy: `column.is_(None)` / `column.is_(True)` statt `== None` / `== True`.
- Secrets nie loggen; `SecretStr` + `.get_secret_value()` nutzen (siehe `app/config.py`).
- Frontend: kein `any`, kein `@ts-ignore`; API-Fehler über `parseErrorResponse()`.

## Sicherheit / Compliance

CI-Security: Bandit, pip-audit, npm audit, Semgrep, Trivy, detect-secrets
(`.github/workflows/security.yml`). Schwachstellen vertraulich melden — `SECURITY.md`.
