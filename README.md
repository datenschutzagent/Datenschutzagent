# DatenschutzAgent

Assistent für den Datenschutz in Forschungsvorhaben: Vorgänge (Cases) verwalten, Dokumente hochladen, Playbook-Checks (LLM-gestützt) ausführen und Findings, DSB-Berichte sowie VVT-Normalisierung nutzen.

Ursprüngliches Design: [Figma – DatenschutzAgent](https://www.figma.com/design/cNgohBB9L3a2qlSZskVZuh/DatenschutzAgent).

## Dokumentation

Die vollständige Dokumentation (Schnellstart, Benutzerhandbuch, Administration, Konfiguration, API, Architektur, Roadmap) befindet sich unter **MkDocs**:

- **Lokal anzeigen:** Aus dem Projektroot `mkdocs serve -f mkdocs/mkdocs.yml` (Doku unter `http://localhost:8000`) oder aus `mkdocs/`: `mkdocs serve`.
- **Build:** `mkdocs build -f mkdocs/mkdocs.yml` (Ausgabe in `mkdocs/site/`).
- **Voraussetzung:** `pip install mkdocs mkdocs-material` (oder in einer venv).

## Kurzüberblick

- **Tech-Stack:** Frontend: React (Vite), Tailwind, Radix UI. Backend: FastAPI, PostgreSQL, optional Celery + Redis, optional Weaviate (RAG). LLM: Ollama (lokal oder im Netzwerk).
- **Schnellstart:** `.env` aus `.env.example` anlegen, dann `docker compose up -d`. Frontend: Port 3002, Backend: Port 8002. Ollama separat betreiben und in `.env` unter `OLLAMA_BASE_URL` angeben.
- **Tests:** Frontend: `npm run test`. Backend: im Verzeichnis `backend` mit `DATABASE_URL`: `pytest tests/ -v`.

Alle weiteren Themen (Migrationen, OIDC, RBAC, CLI, Konfiguration) siehe [Dokumentation](#dokumentation).
