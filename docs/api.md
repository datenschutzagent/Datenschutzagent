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
| GET | `/api/v1/cases/{id}/activities` | Aktivitätslog für den Case (run_checks, finding_status_updated). Response: `[{ "id", "case_id", "event_type", "payload", "created_at" }]`, sortiert nach Zeit absteigend. |
| GET | `/api/v1/cases/{id}/vvt-normalization` | VVT-Normalisierung für den Case (erstes VVT-Dokument). Optional: `?document_id=uuid` für ein bestimmtes VVT-Dokument. Liefert kanonische VVT-Felder und Template-Erkennung (LLM). |
| GET | `/api/v1/cases/{id}/vvt-normalization/export` | VVT-Normalisierung als CSV exportieren. Query: `format=csv` (Standard), optional `document_id=uuid`. Response: `text/csv` mit `Content-Disposition: attachment`; Spalten: document_name, source_template, field_name, status, canonical_value, evidence, finding. |
| GET | `/api/v1/cases/{id}/dsb-report` | DSB Summary Report. Query: `format=markdown` (Standard) oder `format=json`. Markdown: Download mit `Content-Disposition: attachment`. JSON: Struktur mit case_id, case_title, generated_at, status, summary (total_documents, total_findings, critical_findings, high_findings, dsfa_required, vvt_completeness), risks, recommendations, open_questions, next_steps. |
| POST | `/api/v1/cases/{id}/run-checks` | Playbook-Checks für den Case ausführen; Body: `{ "playbook_id": "uuid" }`. Findings werden persistiert. |
| GET | `/api/v1/cases/{id}/annotated-documents` | Liste der Dokumente mit Findings, die als annotierte DOCX herunterladbar sind. Response: `[{ "document_id", "document_name", "finding_count" }]`. |
| GET | `/api/v1/cases/{id}/annotated-documents/{document_id}` | Annotierte DOCX (Dokumentinhalt + Findings-Abschnitt) herunterladen. Response: `application/vnd.openxmlformats-officedocument.wordprocessingml.document` mit Content-Disposition. |

### Documents

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/documents/` | Dokumente auflisten (optional `case_id`). |
| GET | `/api/v1/documents/{id}` | Einzelnes Dokument (Metadaten). |
| POST | `/api/v1/documents/` | Einzelnes Dokument hochladen (Form: `case_id`, `file`, `document_type`, `uploaded_by`). Textextraktion beim Upload; Ergebnis in `Document.content`. |
| POST | `/api/v1/documents/bulk` | Mehrere Dokumente in einem Request hochladen (Form: `case_id`, `files` (mehrere Dateien), `document_type`, `uploaded_by`). Gleicher Typ für alle; Response: Liste der angelegten Dokumente (201). |
| DELETE | `/api/v1/documents/{id}` | Dokument löschen (DB + Storage, 204). |

### Playbooks

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/playbooks/` | Alle Playbooks. |
| POST | `/api/v1/playbooks/` | Playbook anlegen (Body: `name`, `version`, `content`, optional `case_type`, `department`). |
| GET | `/api/v1/playbooks/{id}` | Ein Playbook. |
| PATCH | `/api/v1/playbooks/{id}` | Playbook aktualisieren (partial). |
| DELETE | `/api/v1/playbooks/{id}` | Playbook löschen (204). |

### Findings

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| PATCH | `/api/v1/findings/{id}` | Finding aktualisieren (z. B. Status: open, accepted, overruled, fixed). Body: `{ "status": "…" }`. |

### Sonstiges

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/health` | Health-Check (ohne Prefix `/api/v1`). |

### Umgesetzt (Stand Roadmap)

*   Run-Checks, DELETE Document, PATCH/DELETE Playbook, PATCH Finding (Status), GET VVT-Normalisierung, GET VVT-Export (CSV), GET DSB-Report (Markdown/JSON), GET annotierte Dokumente (Liste + Download DOCX), **Audit-Log und GET /cases/{id}/activities** sind implementiert.
