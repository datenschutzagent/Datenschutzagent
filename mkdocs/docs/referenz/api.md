# API Reference

Das Backend ist mit FastAPI umgesetzt. Interaktive Doku:

*   **Swagger UI:** `http://localhost:8002/docs` (Docker) bzw. `http://localhost:8000/docs` (lokal)
*   **ReDoc:** `http://localhost:8002/redoc` (Docker) bzw. `http://localhost:8000/redoc` (lokal)

---

## Endpoints

### Auth (öffentlich, kein Token)

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/auth/config` | OIDC-Konfiguration für das Frontend (ohne Authentifizierung). Response: `oidc_enabled`, `oidc_issuer_url`, `oidc_client_id`, `oidc_scopes` (Array), bei aktivem OIDC zusätzlich `authorization_endpoint`, `token_endpoint`, `end_session_endpoint` (aus Issuer Discovery). |

### Me (aktueller User / Profil)

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/me` | Aktuellen User liefern. Bei **OIDC aktiv:** erfordert `Authorization: Bearer <JWT>`; User wird aus Token (`sub`) ermittelt bzw. bei erstem Login in Tabelle `users` angelegt (`oidc_sub`). Bei **OIDC inaktiv:** aus `CURRENT_USER_ID` oder Default-User. Response: `id`, `display_name`, `email`, `role` (`viewer` \| `editor` \| `admin`), `preferences`, `created_at`, `updated_at`. |
| PATCH | `/api/v1/me` | Profil aktualisieren. Body: optional `display_name`, optional `email`, optional `preferences` (Objekt mit `theme` (light \| dark \| system), `language` (de \| en), `notifications`). Erfordert dieselbe Auth wie GET /me. |

**Hinweis:** Wenn `OIDC_ENABLED=true`, sind alle Routen unter `/api/v1` (außer `GET /api/v1/auth/config`) geschützt; Requests ohne gültigen Bearer-Token erhalten 401. Bei OIDC inaktiv wird der „aktuelle User“ über `CURRENT_USER_ID` (UUID) oder einen Default-User bestimmt. Theme und Sprache aus `preferences` werden im Frontend app-weit angewendet.

**RBAC:** Schreib-Operationen (Cases/Documents/Findings/Playbooks POST, PATCH, DELETE; Run-Checks POST) erfordern Rolle `editor` oder `admin`; andernfalls 403 (Insufficient permissions). Admin-Endpoints (`/api/v1/admin/*`) erfordern Rolle `admin`.

### Admin (Verwaltung, read-only; Rolle `admin` erforderlich)

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/admin/settings` | Generelle Einstellungen (read-only) aus der Konfiguration: `app_name`, `ollama_base_url`, `ollama_enabled`, `ollama_model`, `weaviate_url`, `weaviate_indexing_enabled`, `storage_backend`, `storage_local_path`, `s3_configured`, `s3_bucket`, `celery_enabled`, `celery_broker_configured`. Keine Passwörter/Secrets. **Rolle `admin` erforderlich;** sonst 403. |
| GET | `/api/v1/admin/connections` | Verbindungstests zu Ollama, Weaviate, MinIO, Postgres, Redis. Response: pro Dienst `{ "status": "ok" | "disabled" | "not_configured" | "unreachable", "message"?: "..." }`. **Rolle `admin` erforderlich;** sonst 403. |

### Cases

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/cases/` | Alle Cases auflisten. |
| POST | `/api/v1/cases/` | Case anlegen. |
| GET | `/api/v1/cases/{id}` | Case inkl. Dokumente und Findings. |
| PATCH | `/api/v1/cases/{id}` | Case aktualisieren (Titel, Status, Assignee, …). |
| DELETE | `/api/v1/cases/{id}` | Case löschen (204). |
| GET | `/api/v1/cases/{id}/activities` | Aktivitätslog für den Case (run_checks, finding_status_updated). Response: `[{ "id", "case_id", "event_type", "payload", "created_at" }]`, sortiert nach Zeit absteigend. Bei `event_type=run_checks` enthält `payload`: `playbook_id`, `playbook_name`, `playbook_version`, `model` (Ollama-Modell), `findings_count`, optional `strategies`, optional `rag_fallback`; bei fehlgeschlagenen/übersprungenen Checks zusätzlich `errors` (Liste mit check, scope, document_id, strategy, error) und `skipped_checks_count`. Bei `finding_status_updated`: `finding_id`, `old_status`, `new_status`. |
| GET | `/api/v1/cases/{id}/vvt-normalization` | VVT-Normalisierung für den Case (erstes VVT-Dokument). Optional: `?document_id=uuid` für ein bestimmtes VVT-Dokument. Liefert kanonische VVT-Felder und Template-Erkennung (LLM). |
| GET | `/api/v1/cases/{id}/vvt-normalization/export` | VVT-Normalisierung exportieren. Query: `format=csv` (Standard) oder `format=docx` (Ziel-Template); optional `document_id=uuid`. CSV: Spalten document_name, source_template, field_name, status, canonical_value, evidence, finding. DOCX: Dokumentname, erkanntes Template, Tabelle der Felder. |
| GET | `/api/v1/cases/{id}/dsb-report` | DSB Summary Report. Query: `format=markdown` (Standard) oder `format=json`. Markdown: Download mit `Content-Disposition: attachment`. JSON: Struktur mit case_id, case_title, generated_at, status, summary (total_documents, total_findings, critical_findings, high_findings, dsfa_required, vvt_completeness), risks, recommendations, open_questions, next_steps. |
| GET | `/api/v1/cases/{id}/run-checks/status` | Status des letzten Run-Checks (für Polling). Response: `{ "status": "completed" | "never_run", "last_run": { "id", "case_id", "event_type", "payload", "created_at" } \| null }`. |
| POST | `/api/v1/cases/{id}/run-checks` | Playbook-Checks für den Case ausführen; Body: `{ "playbook_id": "uuid", "strategies": ["full_text"] \| ["rag"] \| ["full_text", "rag"] }`. Default `strategies`: `["full_text"]`. **Strategien:** `full_text` = Volltext des Dokuments (wie bisher); `rag` = relevante Chunks aus Weaviate (Embedding der Anforderung, Abruf top-k Chunks, LLM nur auf diesem Kontext). Beide parallel = Vergleich/Validierung. Findings werden mit `source_strategy` (`full_text` \| `rag`) persistiert. Bei RAG nicht verfügbar: weicher Fallback (nur Volltext), Hinweis im Activity-Payload (`rag_fallback`). Bei fehlgeschlagenen oder übersprungenen Checks: Exceptions werden geloggt; Activity-Payload enthält `errors` (Liste mit check, scope, document_id, strategy, error) und `skipped_checks_count`. Pro Check kann im Playbook `scope` (oder `type`) gesetzt sein: `document` (Standard) oder `case`/`cross_document`. Findings aus Case-Checks haben `document_id=null` (Frontend „Vorgangsbezogen“). |
| GET | `/api/v1/cases/{id}/annotated-documents` | Liste der Dokumente mit Findings, die als annotierte DOCX herunterladbar sind. Response: `[{ "document_id", "document_name", "finding_count" }]`. |
| GET | `/api/v1/cases/{id}/annotated-documents/{document_id}` | Annotiertes Dokument (Dokumentinhalt + Findings) herunterladen. Query: `format=docx` (Standard) oder `format=pdf`. Response: DOCX oder PDF mit Content-Disposition. |

### Documents

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/documents/` | Dokumente auflisten. Query: optional `case_id`, optional `document_type`. Sortierung: nach Typ, dann Version (aufsteigend). Response enthält `version` (v1, v2, … pro Dokumenttyp) und optional `extraction_method` (`"text"` \| `"ocr"`), wenn die Textextraktion per OCR (Ollama Vision) erfolgte. |
| GET | `/api/v1/documents/{id}` | Einzelnes Dokument (Metadaten inkl. `extraction_method`). |
| GET | `/api/v1/documents/{id}/download` | Originaldatei des Dokuments herunterladen (Stream mit Content-Disposition). |
| GET | `/api/v1/documents/{id}/content` | Extrahierter Text des Dokuments (JSON: `{ "content": "..." }`) für Anzeige im Frontend. |
| GET | `/api/v1/documents/{id}/comments` | Kommentare zum Dokument (sortiert nach `created_at`). Response: `[{ "id", "document_id", "case_id", "author", "user_id", "text", "created_at" }]`. |
| POST | `/api/v1/documents/{id}/comments` | Kommentar hinzufügen. Body: `{ "text": "..." }`. **Rolle editor/admin.** Autor aus aktuellem User. |
| PATCH | `/api/v1/documents/{id}` | Dokument aktualisieren (z. B. extrahierter Text). Body: `{ "content": "..." }`. **Rolle editor/admin.** Bei geänderter `content` werden Weaviate-Chunks des Dokuments entfernt (RAG erst nach erneuter Indexierung aktuell). |
| POST | `/api/v1/documents/` | Einzelnes Dokument hochladen (Form: `case_id`, `file`, `document_type`, `uploaded_by`). Version wird pro (case_id, document_type) automatisch vergeben. **Textextraktion:** asynchron (Celery), wenn `CELERY_BROKER_URL` gesetzt; sonst synchron. Response 201 sofort; `Document.content` wird ggf. nachträglich gefüllt. |
| POST | `/api/v1/documents/bulk` | Mehrere Dokumente in einem Request hochladen (Form: `case_id`, `files` (mehrere Dateien), `document_type`, `uploaded_by`). Gleicher Typ für alle; Version pro (case_id, document_type) automatisch fortlaufend. Textextraktion asynchron (Celery), wenn konfiguriert. Response: Liste der angelegten Dokumente (201). |
| DELETE | `/api/v1/documents/{id}` | Dokument löschen (DB + Storage, 204). |

### Departments (Fachbereiche / zentrale Einrichtungen)

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/departments` | Liste aller Fachbereiche (FB 01–16) und zentralen Einrichtungen. Kein DB-Zugriff; Daten aus `backend/app/data/fachbereiche.yaml`. Response: `[{ "code", "label", "type", "value" }]`. |

### Playbooks

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/playbooks/` | Alle Playbooks. |
| POST | `/api/v1/playbooks/` | Playbook anlegen (Body: `name`, `version`, `content`, optional `case_type`, `department`). |
| GET | `/api/v1/playbooks/{id}` | Ein Playbook. |
| PATCH | `/api/v1/playbooks/{id}` | Playbook aktualisieren (partial). |
| DELETE | `/api/v1/playbooks/{id}` | Playbook löschen (204). |

**Playbook-YAML und Auto-Import:** Standard-Playbooks liegen als YAML-Dateien in `backend/app/data/playbooks/` (Format: `name`, `version`, `department`, optional `case_type`, `checks: [{ name, instruction, optional instruction_en, optional scope/type: document | case }]`). Beim ersten Start der Anwendung wird, wenn die Playbook-Tabelle leer ist, automatisch aus diesem Verzeichnis importiert. Optional: `PLAYBOOKS_SEED_DIR` für anderes Verzeichnis. **Sprache:** Die Case-Sprache (`language`) wird bei Run-Checks und VVT-Normalisierung genutzt: LLM-Prompts erhalten einen Sprachhinweis (DE/EN); bei `language` en oder de_en kann pro Check `instruction_en` verwendet werden.

### Findings

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| PATCH | `/api/v1/findings/{id}` | Finding aktualisieren (z. B. Status: open, accepted, overruled, fixed). Body: `{ "status": "…" }`. |
| (in Case-Response) | — | Findings enthalten optional `source_strategy`: `"full_text"` \| `"rag"` (welche Run-Checks-Strategie das Finding erzeugt hat). |

### Sonstiges

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/health` | Health-Check (ohne Prefix `/api/v1`). |

### Umgesetzt (Stand Roadmap)

*   Run-Checks (inkl. **Cross-Document-Checks**), DELETE Document, PATCH/DELETE Playbook, PATCH Finding (Status), GET VVT-Normalisierung, GET VVT-Export (CSV + **DOCX** via `?format=docx`), GET DSB-Report (Markdown/JSON), GET annotierte Dokumente (Liste + Download DOCX/**PDF** via `?format=pdf`), **Audit-Log** (Payload bei `run_checks`: playbook_version, model) und GET /cases/{id}/activities sind implementiert.
*   **Dokument-Versionierung:** Version pro (case_id, document_type) beim Upload automatisch; GET /documents mit optionalem `document_type`; Sortierung nach Typ, Version; Case-Response dokumente sortiert; Frontend zeigt v1, v2, … und Hinweis bei Upload.
*   **Asynchrone Jobs (Celery + Redis):** Celery-Worker in docker-compose; Task `extract_document_text` für Textextraktion nach Upload. Upload gibt sofort 201; Extraktion läuft im Hintergrund. Bei fehlendem Broker läuft Extraktion weiterhin synchron. **GET /cases/{id}/run-checks/status** für Status des letzten Run-Checks (Polling). Frontend optional unverändert (kein Polling für Extraktion).
*   **Fachbereiche:** `GET /api/v1/departments` aus Konfiguration (`data/fachbereiche.yaml`). **Playbook-YAML:** Standard-Playbooks in `data/playbooks/`, Auto-Import bei leerer Playbook-Tabelle; Checks unterstützen optional `scope`/`type`. **Frontend Playbook-CRUD:** Anlegen (Dialog), Bearbeiten, Archivieren, Löschen, Duplizieren auf Playbook-Detail-Seite. **Frontend:** Findings mit `document_id=null` werden als „Vorgangsbezogen“ angezeigt.
*   **OCR (gescannte PDFs):** Bei textarmen PDFs wird automatisch Ollama Vision (konfigurierbar: `OLLAMA_OCR_MODEL`, z. B. qwen2.5-vl) genutzt; PDF-Seiten werden als Bilder an das Modell gesendet. Document-Feld `extraction_method` (`text` \| `ocr`); Frontend zeigt bei `ocr` den Badge „Text per OCR extrahiert“.
*   **DE/EN-Sprachunterstützung:** Run-Checks und VVT-Normalisierung nutzen die Case-Sprache (`language`); Check Runner und VVT-Service erhalten einen optionalen Parameter `language`, die LLM-Prompts enthalten einen Sprachhinweis. Playbook-Checks unterstützen optional `instruction_en` (bei Case-Sprache en/de_en).
*   **User-Profil und Verwaltung:** `GET/PATCH /api/v1/me` für aktuellen User (Profil, Präferenzen Theme/Sprache). Tabelle `users`, Default-User beim Start; optional `CURRENT_USER_ID` (wenn OIDC aus). **Auth:** Bei `OIDC_ENABLED=true` JWT-Validierung (JWKS), User-Sync per `oidc_sub`; `GET /api/v1/auth/config` öffentlich für Frontend-Login. **Admin:** `GET /api/v1/admin/settings` (read-only Einstellungen), `GET /api/v1/admin/connections` (Verbindungstests). Frontend: Login/Logout (OIDC), Nutzeranzeige im Header, Seite „Mein Profil“, Seite „Verwaltung“; Theme und Sprache aus dem Profil.
