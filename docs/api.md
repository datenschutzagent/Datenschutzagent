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
| GET | `/api/v1/cases/{id}/vvt-normalization` | VVT-Normalisierung für den Case (erstes VVT-Dokument). Optional: `?document_id=uuid` für ein bestimmtes VVT-Dokument. Liefert kanonische VVT-Felder und Template-Erkennung (LLM). |
| POST | `/api/v1/cases/{id}/run-checks` | Playbook-Checks für den Case ausführen; Body: `{ "playbook_id": "uuid" }`. Findings werden persistiert. |

### Documents

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/documents/` | Dokumente auflisten (optional `case_id`). |
| GET | `/api/v1/documents/{id}` | Einzelnes Dokument (Metadaten). |
| POST | `/api/v1/documents/` | Dokument hochladen (Form: `case_id`, `file`, `document_type`, `uploaded_by`). Textextraktion läuft beim Upload; Ergebnis in `Document.content`. |

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

*   Run-Checks, DELETE Document, PATCH/DELETE Playbook, PATCH Finding (Status), GET VVT-Normalisierung sind implementiert.
