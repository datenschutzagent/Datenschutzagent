# Troubleshooting & FAQ

Häufige Probleme und Lösungen für DatenschutzAgent.

---

## Installation & Deployment

### Docker-Compose startet nicht

**Problem:** `docker-compose up` schlägt fehl.

**Lösung:**
```bash
# 1. Docker-Status prüfen
docker --version
docker-compose --version

# 2. Ports prüfen (3002, 8002, 5432 etc.)
lsof -i :3002
lsof -i :8002

# 3. Alte Container entfernen
docker-compose down
docker-compose rm -f

# 4. Neu starten
docker-compose up -d

# 5. Logs prüfen
docker-compose logs -f
```

### Port bereits belegt

**Problem:** „Address already in use"

**Lösung:**
```bash
# Option 1: Prozess killen
lsof -i :8002 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Option 2: Andere Ports in docker-compose.yml nutzen
# Change: ports: "8002:8000" → "8003:8000"
```

### Datenbank-Verbindung fehlgeschlagen

**Problem:** Backend kann Postgres nicht erreichen.

**Lösung:**
```bash
# 1. Container läuft?
docker-compose ps

# 2. Netzwerk prüfen
docker network ls
docker network inspect datenschutzagent_default

# 3. DATABASE_URL prüfen
echo $DATABASE_URL

# 4. Direkter Test
psql $DATABASE_URL -c "SELECT 1;"

# 5. Im Docker-Container
docker-compose exec postgres psql -U postgres -d datenschutzagent
```

---

## Backend-Probleme

### Server startet nicht

**Problem:** `uvicorn` läuft nicht.

**Lösung:**
```bash
# 1. Python-Version prüfen
python --version  # ≥ 3.9 erforderlich

# 2. Dependencies prüfen
cd backend
pip install -r requirements.txt

# 3. Environment-Variablen
source ../.env  # oder load in shell

# 4. Mit Debug-Output starten
uvicorn app.main:app --reload --log-level debug

# 5. Syntax-Fehler?
python -m py_compile app/main.py
```

### Database-Migrationen fehlgeschlagen

**Problem:** `alembic upgrade head` schlägt fehl.

**Lösung:**
```bash
# 1. Migrations-Status
alembic current

# 2. Vorherige Version zurück
alembic downgrade -1

# 3. Neu probieren
alembic upgrade head

# 4. Wenn stuck: Fallback
alembic stamp head  # Markiere als current ohne auszuführen
```

### Ollama nicht erreichbar

**Problem:** LLM-Calls schlagen fehl mit „Connection refused".

**Lösung:**
```bash
# 1. Ollama läuft?
ollama list

# 2. URL prüfen
echo $OLLAMA_BASE_URL

# 3. Test-Request
curl $OLLAMA_BASE_URL/api/tags

# 4. Docker-Host
# Im Docker Container: OLLAMA_BASE_URL=http://host.docker.internal:11434

# 5. Model geladen?
ollama pull llama2
```

### Weaviate nicht erreichbar

**Problem:** RAG-Checks schlagen fehl.

**Lösung:**
```bash
# 1. Weaviate Container prüfen
docker-compose ps

# 2. Health-Check
curl http://localhost:8080/v1/.well-known/ready

# 3. Neu starten
docker-compose restart weaviate

# 4. Daten löschen
docker-compose exec weaviate \
  curl -X DELETE http://localhost:8080/v1/schema

# 5. In .env deaktivieren
WEAVIATE_INDEXING_ENABLED=false
```

### Tests fehlgeschlagen

**Problem:** `pytest tests/` schlägt fehl.

**Lösung:**
```bash
# 1. Test-Database prüfen
export DATABASE_URL=postgresql://postgres:password@localhost:5432/test_db

# 2. Isolation prüfen
pytest tests/test_api.py::test_specific -v -s

# 3. Fixtures prüfen
# conftest.py für Setup

# 4. Mit Coverage
pytest tests/ --cov=app --cov-report=term-missing

# 5. Einzelne Test
pytest tests/test_api.py::TestCases::test_create_case -xvs
```

### Authentifizierung fehlgeschlagen

**Problem:** 401 Unauthorized bei API-Calls.

**Lösung:**
```bash
# 1. Token prüfen
echo $JWT_TOKEN  # oder aus OIDC

# 2. Bearer-Header korrekt?
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/me

# 3. OIDC aktiviert?
curl http://localhost:8000/api/v1/auth/config | jq .oidc_enabled

# 4. JWT-Secret
echo $SECRET_KEY  # müss gesetzt sein

# 5. Token-Expiry?
jq -R 'split(".") | .[1] | @base64d | fromjson' <<< "$TOKEN"
```

---

## Frontend-Probleme

### Frontend lädt nicht

**Problem:** Browser zeigt Fehlerseite.

**Lösung:**
```bash
# 1. Dev-Server läuft?
npm run dev

# 2. Port prüfen
lsof -i :5173

# 3. Logs prüfen
# Terminal sollte Vite-Output zeigen

# 4. Browser-Cache löschen
# Ctrl+Shift+Delete (Chrome)

# 5. API-URL korrekt?
# .env VITE_API_BASE_URL=http://localhost:8000
```

### API-Aufrufe fehlgeschlagen (CORS-Fehler)

**Problem:** „Access to XMLHttpRequest blocked by CORS policy".

**Lösung:**
```bash
# 1. Backend CORS-Konfiguration
# Im .env: CORS_ORIGINS=http://localhost:5173

# 2. Main.py prüfen
# CORSMiddleware sollte hinzugefügt sein

# 3. Beispiel-Konfiguration:
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=CORS_ORIGINS.split(","),
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# 4. Neu starten
# Backend neu starten nach CORS-Änderung
```

### Komponente rendert nicht

**Problem:** React-Komponente zeigt nur Fehlerseite.

**Lösung:**
```bash
# 1. Browser-DevTools öffnen (F12)
# Console → JavaScript-Fehler prüfen

# 2. React DevTools Extension
# https://chrome.google.com/webstore/...react-devtools

# 3. Spezifische Test-Komponente
# npx vitest components/__tests__/MyComponent.test.tsx

# 4. Prop-Types prüfen
# TypeScript sollte Fehler zeigen

# 5. Network-Tab
# Prüfen ob API-Requests erfolgreich sind
```

### Theme-Wechsel funktioniert nicht

**Problem:** Dark Mode wird nicht aktiviert.

**Lösung:**
```bash
# 1. localStorage prüfen
# DevTools → Application → Local Storage

# 2. CSS prüfen
# Sollte `dark:` Klassen nutzen

# 3. Tailwind-Konfiguration
# tailwind.config.js: darkMode: "class"

# 4. HTML-Element
# <html class="dark"> sollte gesetzt sein
```

---

## Daten & Storage

### Dokumente können nicht hochgeladen werden

**Problem:** File-Upload schlägt fehl.

**Lösung:**
```bash
# 1. File-Größe prüfen
# Max: üblicherweise 500 MB

# 2. Format unterstützt?
# DOCX, PDF, XLSX sollten unterstützt sein

# 3. Storage-Backend prüfen
# Local oder MinIO?

# 4. Speicherplatz
# df -h  # Disk-Space prüfen

# 5. Permissions
# chmod 755 /path/to/storage

# 6. Logs
# docker-compose logs backend | grep upload
```

### Dokument-Text ist leer (OCR nicht aktiv)

**Problem:** Gescannte PDFs zeigen keinen Text.

**Lösung:**
```bash
# 1. OLLAMA_OCR_MODEL prüfen
echo $OLLAMA_OCR_MODEL  # z.B. qwen2.5-vl

# 2. Model geladen?
ollama pull qwen2.5-vl

# 3. Dokument neu hochladen
# OCR läuft beim Upload

# 4. Celery prüfen (asynchron)
# docker-compose logs celery

# 5. Manuell testen
# curl -F "file=@scan.pdf" http://localhost:8000/api/v1/documents/
```

### Findings sind verschwunden

**Problem:** Nach Case-Update sind Findings weg.

**Lösung:**
```bash
# 1. Database-Backup existiert?
# Nur bei Datenverlust relevant

# 2. Activity-Log prüfen
# GET /api/v1/cases/{id}/activities

# 3. Datenbankabfrage
psql $DATABASE_URL
SELECT * FROM findings WHERE case_id = 'xxx';

# 4. Soft-Delete?
# Findings sollten nicht dauerhaft gelöscht werden

# 5. Daten-Recovery
# Bei Backup: pg_restore
```

### MinIO S3-Fehler

**Problem:** Storage-Backend kann auf Objekte nicht zugreifen.

**Lösung:**
```bash
# 1. MinIO läuft?
docker-compose ps | grep minio

# 2. Credentials prüfen
# .env: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD

# 3. Bucket existiert?
# Admin-Panel: http://localhost:9001

# 4. Connectivity
# docker-compose exec backend \
#   curl http://minio:9000/minio/health/live

# 5. Logs
docker-compose logs minio | tail -20
```

---

## Performance & Optimierung

### System läuft langsam

**Problem:** Anfragen dauern lange.

**Lösung:**
```bash
# 1. Datenbank-Queries
# PostgreSQL logs: SELECT query_time FROM pg_stat_statements

# 2. N+1 Problem
# Backend: überprüfe Eager Loading (SQLAlchemy selectinload)

# 3. Frontend-Bundle
# npm run build
# Siehe build output für Chunk-Größen

# 4. RAM/CPU
# docker stats

# 5. Indizes fehlend?
# psql > \d cases
# Prüfe auf INDEX
```

### Große Case-Exports sind langsam

**Problem:** VVT/DSB-Report exportieren dauert lange.

**Lösung:**
```bash
# 1. Cache-Headers prüfen
# Cache-Control für Reports

# 2. Streaming-Response nutzen
# Response sollte streamen, nicht Buffer

# 3. Datenbank-Performance
# Query-Optimierung für Bulk-Reports

# 4. Limits
# MAX_FINDINGS_PER_EXPORT prüfen
```

---

## Sicherheit & Compliance

### Authentifizierung funktioniert nicht

**Problem:** OIDC-Login schlägt fehl.

**Lösung:**
```bash
# 1. OIDC-Konfiguration
echo $OIDC_ISSUER_URL
echo $OIDC_CLIENT_ID

# 2. OIDC-Provider
# Issuer-URL im Browser testen:
# https://provider.example.com/.well-known/openid-configuration

# 3. Redirect-URI
# Muss in OIDC-Provider konfiguriert sein
# http://localhost:3002/callback

# 4. JWT-Validierung
# OIDC_AUDIENCE muss korrekt sein

# 5. Lokale Auth deaktivieren
# OIDC_ENABLED=true
```

### RBAC funktioniert nicht

**Problem:** Benutzer mit Editor-Rolle kann nicht editieren.

**Lösung:**
```bash
# 1. Benutzer-Rolle prüfen
# GET /api/v1/me → role field

# 2. Endpoint-Permission
# require_roles("editor", "admin") prüfen

# 3. Datenbank-Daten
psql $DATABASE_URL
SELECT id, display_name, role FROM users;

# 4. Token-Claims
jq -R 'split(".") | .[1] | @base64d | fromjson' <<< "$TOKEN" | grep role
```

### Sensible Daten im Log

**Problem:** Logs enthalten Passwörter/Secrets.

**Lösung:**
```bash
# 1. Logging-Level
# DEBUG-Level senken, nur INFO/WARNING in Prod

# 2. Secrets ausschließen
# logging.filters für Filterung

# 3. Log-Ausgabe prüfen
# Passwords, Tokens sollten masked sein
```

---

## FAQ

### Kann ich externe LLM-Provider nutzen?

**A:** Ja, OpenAI über PydanticAI. Konfiguriere in `.env`:
```bash
OLLAMA_ENABLED=false
OPENAI_API_KEY=sk-...
```

### Unterstützt das System PDF-Extraktion?

**A:** Ja, via PyMuPDF (`pymupdf`). OCR mit Ollama optional (`OLLAMA_OCR_MODEL`).

### Kann ich Daten exportieren/importieren?

**A:** Ja, REST-API mit `?export=json` oder Playbook-Import via YAML.

### Wird Datenverschlüsselung unterstützt?

**A:** Database: PostgreSQL mit SSL. Storage: MinIO mit S3-Encryption konfigurierbar.

### Wie scale ich das System?

**A:** 
- Load-Balancing: mehrere Backend-Instanzen
- Database: PostgreSQL Replication
- Cache: Redis für häufige Queries
- Task-Queue: Celery horizontal skalierbar

### Kann ich die Dokumentation hosten?

**A:** Ja, `mkdocs build` generiert statisches HTML. Dann in Nginx, GitHub Pages, etc. hosten.

---

## Support & Community

- **Bugs:** GitHub Issues
- **Dokumentation:** MkDocs lokal bauen: `mkdocs serve`
- **Code:** GitHub PRs
- **Chat:** (Falls vorhanden) Slack/Discord
