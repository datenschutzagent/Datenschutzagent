# API Reference

Das Backend ist mit FastAPI umgesetzt. Interaktive Doku:

*   **Swagger UI:** `http://localhost:8000/docs`
*   **ReDoc:** `http://localhost:8000/redoc`

---

## Endpoints

### Cases

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/cases/` | Alle Cases auflisten. |
| POST | `/api/v1/cases/` | Case anlegen. |
| GET | `/api/v1/cases/{id}` | Case inkl. Dokumente und Findings. |
| PATCH | `/api/v1/cases/{id}` | Case aktualisieren (Titel, Status, Assignee, …). |
| DELETE | `/api/v1/cases/{id}` | Case löschen (204). |
| GET | `/api/v1/cases/{id}/activities` | Aktivitätslog für den Case (run_checks, finding_status_updated). Response: `[{ "id", "case_id", "event_type", "payload", "created_at" }]`, sortiert nach Zeit absteigend. Bei `event_type=run_checks` enthält `payload`: `playbook_id`, `playbook_name`, `playbook_version`, `model` (Ollama-Modell), `findings_count`. Bei `finding_status_updated`: `finding_id`, `old_status`, `new_status`. |
| GET | `/api/v1/cases/{id}/vvt-normalization` | VVT-Normalisierung für den Case (erstes VVT-Dokument). Optional: `?document_id=uuid` für ein bestimmtes VVT-Dokument. Liefert kanonische VVT-Felder und Template-Erkennung (LLM). |
| GET | `/api/v1/cases/{id}/vvt-normalization/export` | VVT-Normalisierung exportieren. Query: `format=csv` (Standard) oder `format=docx` (Ziel-Template); optional `document_id=uuid`. CSV: Spalten document_name, source_template, field_name, status, canonical_value, evidence, finding. DOCX: Dokumentname, erkanntes Template, Tabelle der Felder. |
| GET | `/api/v1/cases/{id}/dsb-report` | DSB Summary Report. Query: `format=markdown` (Standard) oder `format=json`. Markdown: Download mit `Content-Disposition: attachment`. JSON: Struktur mit case_id, case_title, generated_at, status, summary (total_documents, total_findings, critical_findings, high_findings, dsfa_required, vvt_completeness), risks, recommendations, open_questions, next_steps. |
| GET | `/api/v1/cases/{id}/run-checks/status` | Status des letzten Run-Checks (für Polling). Response: `{ "status": "completed" | "never_run", "last_run": { "id", "case_id", "event_type", "payload", "created_at" } \| null }`. |
| POST | `/api/v1/cases/{id}/run-checks` | Playbook-Checks für den Case ausführen; Body: `{ "playbook_id": "uuid" }`. Findings werden persistiert. **Trigger:** ausschließlich manuell (z. B. über die Case-Detail-Seite, Button „Playbook-Checks ausführen“); kein automatischer oder zeitgesteuerter Lauf. Pro Check kann im Playbook `scope` (oder `type`) gesetzt sein: `document` (Standard, ein Check pro Dokument) oder `case`/`cross_document` (ein Check über alle Dokumente). Findings aus Case-Checks haben `document_id=null` (Frontend zeigt sie als „Vorgangsbezogen“). |
| GET | `/api/v1/cases/{id}/annotated-documents` | Liste der Dokumente mit Findings, die als annotierte DOCX herunterladbar sind. Response: `[{ "document_id", "document_name", "finding_count" }]`. |
| GET | `/api/v1/cases/{id}/annotated-documents/{document_id}` | Annotiertes Dokument (Dokumentinhalt + Findings) herunterladen. Query: `format=docx` (Standard) oder `format=pdf`. Response: DOCX oder PDF mit Content-Disposition. |

### Documents

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/documents/` | Dokumente auflisten. Query: optional `case_id`, optional `document_type`. Sortierung: nach Typ, dann Version (aufsteigend). Response enthält `version` (v1, v2, … pro Dokumenttyp) und optional `extraction_method` (`"text"` \| `"ocr"`), wenn die Textextraktion per OCR (Ollama Vision) erfolgte. |
| GET | `/api/v1/documents/{id}` | Einzelnes Dokument (Metadaten inkl. `extraction_method`). |
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

**Playbook-YAML und Auto-Import:** Standard-Playbooks liegen als YAML-Dateien in `backend/app/data/playbooks/` (Format: `name`, `version`, `department`, optional `case_type`, `checks: [{ name, instruction, optional scope/type: document | case }]`). Beim ersten Start der Anwendung wird, wenn die Playbook-Tabelle leer ist, automatisch aus diesem Verzeichnis importiert. Optional: `PLAYBOOKS_SEED_DIR` für anderes Verzeichnis.

### Findings

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| PATCH | `/api/v1/findings/{id}` | Finding aktualisieren (z. B. Status: open, accepted, overruled, fixed). Body: `{ "status": "…" }`. |

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
