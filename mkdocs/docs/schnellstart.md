# Schnellstart

## Mit Docker (empfohlen)

**Voraussetzungen:** Docker, Docker Compose, Ollama (lokal oder im Netz erreichbar).

1. **Umgebung:** `.env` anlegen (Kopie von `.env.example` im Projektroot). Wichtig: `OLLAMA_BASE_URL` (z. B. `http://host.docker.internal:11434` für Ollama auf dem Host). Weitere Optionen siehe [Konfiguration](konfiguration.md).

2. **Starten:**
   ```bash
   docker compose up -d
   ```

3. **Zugriff:**
   * Frontend: `http://localhost:3002`
   * Backend/API: `http://localhost:8002`
   * API-Doku (Swagger): `http://localhost:8002/docs`

4. **Ollama:** Muss separat laufen (wird nicht mit Docker gestartet). Unter `OLLAMA_BASE_URL` erreichbar machen; aus dem Backend-Container z. B. `http://host.docker.internal:11434` (Docker Desktop) oder die IP des Hosts im LAN.

---

## Lokal (ohne Docker)

1. **Umgebung:** `.env` im Projektroot (siehe [.env.example](https://github.com/...) bzw. [Konfiguration](konfiguration.md)). Mindestens: `OLLAMA_BASE_URL` (z. B. `http://localhost:11434`), `DATABASE_URL`, optional `CELERY_BROKER_URL`, `CORS_ORIGINS`.

2. **PostgreSQL** laufen lassen (lokal oder in Docker).

3. **Backend:**  
   Im Verzeichnis `backend`: `pip install -r requirements.txt`, dann:
   ```bash
   uvicorn app.main:app --reload
   ```
   Backend dann unter `http://localhost:8000` (bzw. konfigurierter Port).

4. **Frontend:**  
   Im Projektroot: `npm install`, dann `npm run dev`. Dev-Server unter `http://localhost:3002` (bzw. Vite-Port).

5. **Ollama:** Für Playbook-Checks und optional OCR muss Ollama laufen und unter `OLLAMA_BASE_URL` erreichbar sein.

---

## Tests

* **Frontend:** `npm run test` (Vitest). Watch: `npm run test:watch`.
* **Backend:** Im Verzeichnis `backend` mit gesetzter `DATABASE_URL`: `pytest tests/ -v`.

Details zu Migrationen, Profil und Verwaltung siehe [Verwaltung](administration/verwaltung.md) und [Datenbank-Migrationen](administration/migrationen.md).
