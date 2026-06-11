# Beitragen zu DatenschutzAgent

Danke für Ihr Interesse! Diese Anleitung fasst Setup, Qualitäts-Gates und den
Beitrags-Workflow zusammen. Ausführliche Doku: siehe `mkdocs/` bzw. README.

## Entwicklungs-Setup

Voraussetzungen: Docker + Docker Compose, Node.js 20, Python 3.12.

```bash
cp .env.example .env        # Werte anpassen (siehe Kommentare in der Datei)
docker compose up -d        # Postgres, MinIO, Redis, Weaviate, Backend, Worker, Frontend
```

Frontend: Port 3002 · Backend/Swagger: Port 8002 · Doku: `mkdocs serve -f mkdocs/mkdocs.yml`.

## Qualitäts-Gates (vor jedem Commit)

Installieren Sie die Pre-Commit-Hooks – sie erzwingen Format, Lint und
Secret-Scanning lokal:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files   # einmalig über das ganze Repo
```

Dieselben Gates laufen in CI (`.github/workflows/test.yml`, `security.yml`).
Bitte stellen Sie sicher, dass folgendes lokal grün ist:

**Backend** (im Verzeichnis `backend/`):

```bash
ruff check .            # Lint (Konfiguration: ruff.toml)
black --check .         # Formatierung
pytest tests/ -v        # Tests (benötigt DATABASE_URL auf eine Postgres-Instanz)
python -m evals.run     # Offline-Qualitäts-Gate (Extraktion/Grounding)
```

**Frontend** (Projektwurzel):

```bash
npm run lint            # ESLint
npm run typecheck       # tsc --noEmit (Typprüfung)
npm run test            # Vitest
npm run test:e2e        # Playwright E2E (benötigt laufenden Stack)
```

> Hinweis: Die Frontend-Typprüfung (`npm run typecheck`) wird derzeit auf einen
> sauberen Stand gebracht; siehe `CHANGELOG.md` / offene Aufgaben.

## Branch- & Commit-Konventionen

- Entwickeln Sie auf einem Feature-Branch, niemals direkt auf `main`.
- Schreiben Sie aussagekräftige Commit-Messages (was und warum).
- Halten Sie PRs fokussiert; aktualisieren Sie Doku (`mkdocs/`) bei
  Verhaltens-/API-Änderungen.

## Datenbank-Migrationen

Schema-Änderungen erfolgen über **Alembic** (einzige Quelle der Wahrheit):

```bash
cd backend
alembic revision -m "beschreibung"   # neue Migration
alembic upgrade head                 # anwenden (läuft auch im Container-Entrypoint)
```

Historische rohe SQL-Skripte unter `backend/migrations/legacy/` sind **nicht**
mehr aktiv (vor dem Alembic-Baseline); bitte keine neuen dort anlegen.

## Sicherheit

Sicherheitslücken bitte vertraulich melden – siehe `SECURITY.md`.
