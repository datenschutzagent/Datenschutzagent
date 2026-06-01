# DatenschutzAgent

Datenschutz-Compliance-Tool für Organisationen jeder Art: Vorgänge (Cases) verwalten, Dokumente hochladen, Playbook-Checks (LLM-gestützt) ausführen und Findings, DSB-Berichte sowie VVT-Normalisierung (DSGVO Art. 30) nutzen.

Einsetzbar für Unternehmen, Behörden, Hochschulen, Krankenhäuser und andere Organisationen — konfigurierbar über Org-Profile ohne Code-Anpassungen.

Ursprüngliches Design: [Figma – DatenschutzAgent](https://www.figma.com/design/cNgohBB9L3a2qlSZskVZuh/DatenschutzAgent).

## Schnellkonfiguration für Ihre Organisation

1. `.env` aus `.env.example` anlegen
2. `ORG_PROFILE=meine-org` setzen und `backend/app/data/org_profiles/meine-org/departments.yaml` erstellen (Vorlage: `org_profiles/example/`)
3. Optional: `ORG_NAME="Meine Organisation GmbH"` für den Frontend-Header
4. Optional: eigene Playbooks als YAML-Dateien in ein Verzeichnis legen und `PLAYBOOKS_SEED_DIR` setzen
5. `docker compose up -d` starten

Mitgelieferte Profile: **`default`** (generisch), **`goethe`** (Goethe-Universität Frankfurt), **`example`** (Demonstrationsprofil).

## Dokumentation

Die vollständige Dokumentation (Schnellstart, Benutzerhandbuch, Administration, Konfiguration, API, Architektur, Roadmap) befindet sich unter **MkDocs**:

- **Lokal anzeigen:** Aus dem Projektroot `mkdocs serve -f mkdocs/mkdocs.yml` (Doku unter `http://localhost:8000`) oder aus `mkdocs/`: `mkdocs serve`.
- **Build:** `mkdocs build -f mkdocs/mkdocs.yml` (Ausgabe in `mkdocs/site/`).
- **Voraussetzung:** `pip install mkdocs mkdocs-material` (oder in einer venv).

## Kurzüberblick

- **Tech-Stack:** Frontend: React (Vite), Tailwind, Radix UI. Backend: FastAPI, PostgreSQL, optional Celery + Redis, optional Weaviate (RAG). LLM: Ollama (lokal oder im Netzwerk).
- **Schnellstart:** `.env` aus `.env.example` anlegen, dann `docker compose up -d`. Frontend: Port 3002 (API unter `/api/v1` am selben Origin), Backend direkt: Port 8002 (Swagger/Docs). Ollama separat betreiben und in `.env` unter `OLLAMA_BASE_URL` angeben.
- **Tests:** Frontend: `npm run test`. Backend: im Verzeichnis `backend` mit `DATABASE_URL`: `pytest tests/ -v`.

Alle weiteren Themen (Migrationen, OIDC, RBAC, CLI, Konfiguration) siehe [Dokumentation](#dokumentation).
