# Backend-CLI (Rollen & Einstellungen)

Im Backend-Container steht ein kleines CLI zur Verfügung, mit dem sich Benutzerrollen verwalten und die Systemkonfiguration anzeigen bzw. prüfen lassen.

**Aufruf im Container (aus Projektroot):**

```bash
docker compose run --rm backend python -m app.cli <command> ...
```

**Lokal (ohne Docker):** Im Backend-Verzeichnis mit passender `.env` bzw. `DATABASE_URL`:

```bash
cd backend && python -m app.cli <command> ...
```

## Befehle

### User- und Rollenverwaltung (`users`)

- **Alle User anzeigen** (id, display_name, email, role, oidc_sub):
  ```bash
  docker compose run --rm backend python -m app.cli users list
  ```

- **Rolle setzen** (viewer | editor | admin):
  ```bash
  docker compose run --rm backend python -m app.cli users set-role <user-uuid> editor
  ```

- **Default-User und Hinweis** (wenn OIDC deaktiviert ist, wird dieser User verwendet; hier kann die Rolle gesetzt werden, um Schreibrechte zu erhalten):
  ```bash
  docker compose run --rm backend python -m app.cli users show-default
  ```

Beispiel: Schreibrechte für den Standardnutzer ohne OIDC vergeben:

```bash
docker compose run --rm backend python -m app.cli users set-role 00000000-0000-4000-8000-000000000001 editor
```

### Konfiguration (`config`)

- **Einstellungen anzeigen** (ohne Secrets; z. B. app_name, Ollama, Weaviate, Storage, Celery, OIDC, RBAC-Default-Rolle):
  ```bash
  docker compose run --rm backend python -m app.cli config show
  ```

- **Verbindungstests** (Ollama, Weaviate, Postgres, MinIO, Redis):
  ```bash
  docker compose run --rm backend python -m app.cli config check
  ```

## Hinweis

Die CLI umgeht die API und spricht direkt mit der Datenbank bzw. der Konfiguration. Es werden keine neuen Pip-Abhängigkeiten benötigt (nur stdlib: argparse, asyncio).
