# Konfiguration

Die Anwendung wird über Umgebungsvariablen konfiguriert. Im Projektroot liegt eine Vorlage: **`.env.example`**. Kopieren Sie diese Datei nach `.env` und passen Sie die Werte an.

---

## Datenbank

| Variable | Beschreibung |
| :--- | :--- |
| `DATABASE_URL` | PostgreSQL-Connection-String (z. B. `postgresql+asyncpg://postgres:postgres@localhost:5432/datenschutzagent`). In Docker Compose wird die URL für das Backend automatisch gesetzt. |

---

## LLM-Provider

| Variable | Beschreibung |
| :--- | :--- |
| `LLM_PROVIDER` | Aktiver Provider: `ollama` (Standard) \| `openai` \| `anthropic` \| `openai_compatible`. |
| `LLM_STRUCTURED_OUTPUT_MODE` | Wie das Output-Schema durchgesetzt wird: `tool` (Standard; Tool-Calling), `native` (JSON-Schema-`response_format` → constrained decoding; empfohlen für lokale Server wie vLLM/llama.cpp/Ollama) oder `prompted` (Schema nur im Prompt). Bei Anthropic wird `native` ignoriert. |

### Ollama (`LLM_PROVIDER=ollama`)

| Variable | Beschreibung |
| :--- | :--- |
| `OLLAMA_BASE_URL` | Basis-URL des Ollama-Servers (z. B. `http://localhost:11434` oder aus Docker `http://host.docker.internal:11434`). |
| `OLLAMA_MODEL` | Modell für Inferenz (z. B. `llama3.2`, `mistral`). |
| `OLLAMA_TIMEOUT_SECONDS` | Timeout für LLM-Anfragen in Sekunden (Default z. B. 120). |
| `OLLAMA_ENABLED` | Ollama-Funktionen ein- oder ausschalten. |

### Custom OpenAI-kompatibler Server (`LLM_PROVIDER=openai_compatible`)

Für selbst gehostete Inferenz-Server mit OpenAI-kompatibler API: llama.cpp (`llama-server`), vLLM, LiteLLM, TGI u. a.

| Variable | Beschreibung |
| :--- | :--- |
| `LLM_BASE_URL` | Basis-URL des Servers, z. B. `http://localhost:8000/v1` (vLLM) oder `http://localhost:8080` (llama.cpp). Ein fehlendes `/v1` wird automatisch ergänzt. **Pflicht.** |
| `LLM_MODEL` | Served model name, z. B. `Qwen/Qwen2.5-14B-Instruct`. **Pflicht.** |
| `LLM_API_KEY` | Optionaler API-Key (z. B. vLLM `--api-key`). Leer = ohne Authentifizierung. |

Empfehlung: zusammen mit `LLM_STRUCTURED_OUTPUT_MODE=native` betreiben — vLLM (guided decoding) und llama.cpp (json_schema/GBNF) erzwingen das Output-Schema dann serverseitig, was Schema-Fehler kleiner lokaler Modelle praktisch eliminiert.

### OCR (gescannte PDFs)

Der OCR-Aufruf nutzt das OpenAI-kompatible Chat-Completions-Format (Bild als Base64-Data-URI) und funktioniert damit gegen Ollama, vLLM und llama.cpp. Ohne Override wird der Endpoint vom aktiven Provider abgeleitet (`openai_compatible` → `LLM_BASE_URL`, sonst `OLLAMA_BASE_URL`).

| Variable | Beschreibung |
| :--- | :--- |
| `OLLAMA_OCR_MODEL` | Vision-Modell (z. B. `qwen2.5-vl`, `minicpm-v`). |
| `OLLAMA_OCR_ENABLED` | OCR für textarme PDFs aktivieren. |
| `OCR_BASE_URL` | Optionaler eigener OpenAI-kompatibler Vision-Endpoint (das Vision-Modell läuft oft auf einem anderen Server als das Text-Modell). |
| `OCR_MODEL` | Optionales Modell für `OCR_BASE_URL`; leer = `OLLAMA_OCR_MODEL`. |
| `OCR_API_KEY` | Optionaler API-Key für den OCR-Endpoint. |
| `OCR_MIN_CHARS_PER_PAGE` | Schwellwert Zeichen pro Seite; darunter wird OCR ausgelöst. |
| `OCR_DPI` | Auflösung beim Rendern der PDF-Seiten für OCR. |

---

## CORS

| Variable | Beschreibung |
| :--- | :--- |
| `CORS_ORIGINS` | Kommagetrennte Liste erlaubter Origins (z. B. `http://localhost:3002`, `http://192.168.1.20:3002`). Bei Zugriff über LAN die entsprechende URL ergänzen. |

---

## Frontend-Build

| Variable | Beschreibung |
| :--- | :--- |
| `VITE_API_URL` | Wird nur beim Bau des Frontend-Images genutzt. **Standard (leer):** Same-Origin — die SPA ruft `/api/v1/...` über den Frontend-Port auf; Nginx proxied an den Backend-Container. Nur setzen, wenn Frontend und API auf getrennten Origins laufen. |

---

## Celery (asynchrone Dokument-Extraktion)

| Variable | Beschreibung |
| :--- | :--- |
| `CELERY_BROKER_URL` | Redis-URL für Celery (z. B. `redis://localhost:6379/0`). In Docker setzt docker-compose z. B. `redis://:REDIS_PASSWORD@redis:6379/0` (Passwort ggf. URL-encoden, falls Sonderzeichen enthalten sind). |
| `CELERY_ENABLED` | Wenn nicht gesetzt oder Broker fehlt: Extraktion beim Upload synchron. |

---

## Aktueller User (ohne OIDC)

| Variable | Beschreibung |
| :--- | :--- |
| `CURRENT_USER_ID` | UUID des Users für GET/PATCH `/me`, wenn OIDC deaktiviert ist (z. B. `00000000-0000-4000-8000-000000000001`). |

---

## OAuth2/OIDC (Authentifizierung)

| Variable | Beschreibung |
| :--- | :--- |
| `OIDC_ENABLED` | Bei `true`: alle API-Routen außer `/health` und `GET /api/v1/auth/config` erfordern gültigen Bearer-Token. |
| `OIDC_ISSUER_URL` | Issuer-URL des OIDC-Providers (z. B. Keycloak Realm-URL). |
| `OIDC_CLIENT_ID` | Client-ID der Anwendung. |
| `OIDC_CLIENT_SECRET` | Optional, für Confidential Client. |
| `OIDC_AUDIENCE` | Optional; JWT `aud` muss übereinstimmen. |
| `OIDC_SCOPES` | Gewünschte Scopes (z. B. `openid profile email`). |
| `RBAC_DEFAULT_ROLE` | Default-Rolle für neue Nutzer (erstmaliger OIDC-Login): `viewer` \| `editor` \| `admin`. |

---

## Storage (MinIO, optional)

| Variable | Beschreibung |
| :--- | :--- |
| `STORAGE_BACKEND` | `local` (Standard) oder `minio`. |
| `S3_ENDPOINT_URL` | MinIO/S3-Endpoint (z. B. `http://minio:9000`). |
| `S3_ACCESS_KEY` | S3 Access Key. |
| `S3_SECRET_KEY` | S3 Secret Key. |
| `S3_BUCKET` | Bucket-Name (z. B. `documents`). |

---

## Weaviate (RAG, optional)

Wie die übrigen Dienste wird Weaviate über `.env` konfiguriert. docker-compose liest die Weaviate-Container-Optionen aus denselben Variablen (mit Präfix `WEAVIATE_`). Details siehe [Architektur](referenz/architecture.md).

| Variable | Beschreibung |
| :--- | :--- |
| `WEAVIATE_URL` | URL der Weaviate-Instanz (Backend). In Docker z. B. `http://weaviate:8080`. |
| `WEAVIATE_INDEXING_ENABLED` | RAG-Indexierung nach Textextraktion ein- oder ausschalten. |
| `WEAVIATE_CHUNK_SIZE_CHARS` | Chunk-Größe in Zeichen für die Indexierung (Default 800). |
| `WEAVIATE_CHUNK_OVERLAP_CHARS` | Überlappung zwischen Chunks in Zeichen (Default 100). |
| `WEAVIATE_TOP_K` | Anzahl relevanter Chunks pro RAG-Abfrage (Default 5). |
| `OLLAMA_EMBEDDING_MODEL` | Ollama-Modell für Embeddings (z. B. `nomic-embed-text`). |
| `EMBEDDING_BASE_URL` | Optional: OpenAI-kompatible `/v1/embeddings`-API statt des nativen Ollama-Clients (vLLM, llama.cpp, TEI/Infinity). Ein fehlendes `/v1` wird ergänzt. Damit sind auch stärkere multilinguale Embedder (z. B. `BAAI/bge-m3`, `multilingual-e5`) nutzbar. |
| `EMBEDDING_MODEL` | Modell für `EMBEDDING_BASE_URL`; leer = `OLLAMA_EMBEDDING_MODEL`. |
| `EMBEDDING_API_KEY` | Optionaler API-Key für den Embedding-Endpoint. |
| `WEAVIATE_PERSISTENCE_DATA_PATH` | Persistenzpfad im Weaviate-Container (nur docker-compose; Default `/var/lib/weaviate`). |
| `WEAVIATE_QUERY_DEFAULTS_LIMIT` | Default-Limit für Weaviate-Abfragen im Container (Default 25). |
| `WEAVIATE_CLUSTER_HOSTNAME` | Cluster-Hostname des Weaviate-Containers (Default `node1`). |
