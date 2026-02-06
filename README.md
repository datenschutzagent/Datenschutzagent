# DatenschutzAgent

Assistent für den Datenschutz in Forschungsvorhaben: Vorgänge (Cases) verwalten, Dokumente hochladen, Playbook-Checks (LLM-gestützt) ausführen und Findings, DSB-Berichte sowie VVT-Normalisierung nutzen.

Ursprüngliches Design: [Figma – DatenschutzAgent](https://www.figma.com/design/cNgohBB9L3a2qlSZskVZuh/DatenschutzAgent).

## Tech-Stack

- **Frontend:** React (Vite), Tailwind, Radix UI
- **Backend:** FastAPI, PostgreSQL, optional Celery + Redis, optional Weaviate (RAG)
- **LLM:** Ollama (lokal oder im Netzwerk)

Ausführliche Architektur: [docs/architecture.md](docs/architecture.md). API-Beschreibung: [docs/api.md](docs/api.md).

## Schnellstart (lokal)

1. **Umgebung:** `.env` anlegen (siehe [.env.example](.env.example)). Wichtig: `OLLAMA_BASE_URL` (z. B. `http://localhost:11434`), ggf. `DATABASE_URL`, `CELERY_BROKER_URL`, `CORS_ORIGINS`.

2. **Backend (mit Postgres):**
   - PostgreSQL laufen lassen (lokal oder Docker).
   - Im Backend-Verzeichnis: `pip install -r requirements.txt`, dann `uvicorn app.main:app --reload` (oder über Docker, siehe unten).

3. **Frontend:**  
   `npm install` und `npm run dev` – Dev-Server unter `http://localhost:3002`.

4. **Ollama:** Für Playbook-Checks und OCR muss Ollama laufen und unter `OLLAMA_BASE_URL` erreichbar sein.

## Docker (Backend, DB, Redis, Weaviate, Frontend)

Aus dem Projektroot:

```bash
docker compose up -d
```

Backend: Port 8002, Frontend: Port 3002. Ollama wird nicht mitgestartet – auf dem Host oder im LAN betreiben und in `.env` z. B. `OLLAMA_BASE_URL=http://host.docker.internal:11434` setzen.

Details und Optionen: [docs/architecture.md](docs/architecture.md) (Abschnitt Deployment).

## Tests

- **Frontend:** `npm run test` (Vitest). Watch-Modus: `npm run test:watch`.
- **Backend:** Im Verzeichnis `backend` mit aktivierter venv und gesetzter `DATABASE_URL`: `pytest tests/ -v`.

## Datenbank-Migrationen

Tabellen werden beim Backend-Start per `Base.metadata.create_all` angelegt. Zusätzliche Schema-Änderungen liegen als SQL-Skripte unter [backend/migrations/](backend/migrations/). Diese müssen **einmalig** bei bestehenden Datenbanken ausgeführt werden, z. B.:

```bash
# Einzelne Migration (Beispiel: extraction_method)
docker compose exec -T postgres psql -U postgres -d datenschutzagent < backend/migrations/001_add_document_extraction_method.sql

# Alle Migrationen nacheinander
for f in backend/migrations/*.sql; do docker compose exec -T postgres psql -U postgres -d datenschutzagent < "$f"; done
```

## Benutzerprofil und Verwaltung

- **Mein Profil** (Frontend: `/profile`): Anzeigename und Präferenzen (Theme: hell/dunkel/System; Sprache: DE/EN). Theme und Sprache werden app-weit aus dem Profil übernommen.
- **Verwaltung** (Frontend: `/admin`): Read-only Anzeige der generellen Einstellungen (z. B. Ollama-URL, Weaviate, Storage) und Verbindungstests zu Ollama, Weaviate, MinIO, Postgres, Redis.

### Authentifizierung (OAuth2/OIDC, optional)

Wenn OIDC aktiviert ist (`OIDC_ENABLED=true` in der `.env`), sind alle API-Routen außer `/health` und `GET /api/v1/auth/config` geschützt. Das Frontend leitet nicht eingeloggte Nutzer zum konfigurierten IdP (z. B. Keycloak) weiter und tauscht nach dem Login den Autorisierungscode per PKCE gegen ein Token aus. Konfiguration siehe [.env.example](.env.example) (Abschnitt OAuth2/OIDC). Ohne OIDC wird ein Default-User verwendet; optional kann `CURRENT_USER_ID` gesetzt werden.

### Rollen (RBAC)

Jeder Nutzer hat eine Rolle: **viewer** (nur Lesen), **editor** (Lesen + Erstellen/Bearbeiten/Löschen von Cases, Dokumenten, Playbooks, Run-Checks, Finding-Status), **admin** (wie editor + Zugriff auf Verwaltung: Einstellungen, Verbindungstests). Neue Nutzer (erstmaliger OIDC-Login) erhalten die Default-Rolle aus `RBAC_DEFAULT_ROLE` (z. B. `viewer`). Bestehende User werden per Migration `005_add_user_role.sql` auf `editor` gesetzt. Die Rolle wird in GET `/api/v1/me` zurückgegeben; das Frontend blendet Schreib- und Admin-Aktionen für Nutzer mit Rolle viewer aus.

## Weitere Dokumentation

- [docs/architecture.md](docs/architecture.md) – Systemarchitektur
- [docs/api.md](docs/api.md) – API-Übersicht
- [docs/roadmap.md](docs/roadmap.md) – Roadmap
- [docs/sprint_plan.md](docs/sprint_plan.md) – Sprint-Plan
