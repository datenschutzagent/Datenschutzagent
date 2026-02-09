# Verwaltung

Die **Verwaltung** (Frontend: `/admin`) bietet Administratoren eine read-only Übersicht der Systemeinstellungen und Verbindungstests. Zugriff nur mit Rolle **admin**.

## Einstellungen (read-only)

Über die API `GET /api/v1/admin/settings` werden u. a. angezeigt:

- **App:** app_name
- **Ollama:** ollama_base_url, ollama_enabled, ollama_model
- **Weaviate:** weaviate_url, weaviate_indexing_enabled
- **Storage:** storage_backend, storage_local_path, s3_configured, s3_bucket
- **Celery:** celery_enabled, celery_broker_configured

Keine Passwörter oder Secrets. Die Werte stammen aus der Backend-Konfiguration (Umgebungsvariablen).

## Verbindungstests

`GET /api/v1/admin/connections` prüft die Erreichbarkeit von:

- Ollama
- Weaviate
- MinIO (S3)
- PostgreSQL
- Redis

Pro Dienst wird ein Status zurückgegeben (`ok`, `disabled`, `not_configured`, `unreachable`) und optional eine Meldung. So können Admins schnell erkennen, ob alle benötigten Dienste erreichbar sind.

## Zugriff

- **Frontend:** Link „Verwaltung“ im Menü/Header (nur sichtbar für Nutzer mit Rolle admin). Ohne Admin-Recht erscheint ein Hinweis „Keine Berechtigung“.
- **API:** Beide Endpoints erfordern Rolle `admin`; sonst 403.
