# Nächste Schritte – Plan nach Roadmap & Gap-Analyse

Stand: Nach Abgleich mit Code (Dokument-Versionierung, Celery/Redis, Cross-Document, Artefakte abgeschlossen). Die Punkte 1–7 aus der Gap-Analyse (Run-Checks, Frontend-API, Finding-Status, VVT, Cross-Document, Artefakte, Versionierung, Audit, asynchrone Jobs) sind umgesetzt. **Verbleibende Lücken:** AuthN/AuthZ, OCR, DE/EN-Ausbau, optional Retention/Monitoring. Nächster Sprint: siehe `docs/sprint_plan.md`.

---

## 1. Verifizierter Ist-Stand (Code)

### Backend

| Komponente | Status | Verifiziert |
| :--- | :--- | :--- |
| **Cases** | CRUD inkl. DELETE | ✅ `api/routes/cases.py` – list, get, create, patch, delete |
| **Documents** | Upload, List, Get, DELETE; Extraktion | ✅ `api/routes/documents.py` + `document_processor.py`; `DELETE /documents/{id}` (DB + Storage) |
| **Playbooks** | CRUD inkl. PATCH/DELETE | ✅ `api/routes/playbooks.py` – list, create, get, patch, delete |
| **Findings** | Modell + CaseResponse + eigener Router | ✅ `api/routes/findings.py`: `PATCH /findings/{id}` für Status |
| **Check Runner** | Einzelcheck gegen Dokument | ✅ `services/check_runner.py`: `run_check(document_text, check_instruction)` → `CheckResult` |
| **Run-Checks API** | Implementiert | ✅ `POST /api/v1/cases/{id}/run-checks` in `cases.py`; ruft Check Runner auf, persistiert Findings |
| **Finding-Status API** | Implementiert | ✅ `PATCH /api/v1/findings/{id}` in `findings.py` (Body: `status`) |
| **Ollama Health** | Implementiert | ✅ `/health` prüft bei `ollama_enabled` Ollama (`/api/tags`); bei Fehler `status: degraded`. |
| **VVT** | Implementiert | ✅ `vvt_service.py` (Fingerprinting via source_template, kanonisches Modell, LLM-Mapping), `GET /cases/{id}/vvt-normalization` in `cases.py`; Frontend `VVTNormalizationView` nutzt `getVVTNormalization()` aus `api.ts`. VVT CSV-Export: `GET /cases/{id}/vvt-normalization/export`. Ziel-Template (DOCX) optional. |
| **DSB Report** | Implementiert | ✅ `dsb_report_service.py`, `GET /cases/{id}/dsb-report` (format=json \| markdown); Frontend `DSBReportView`. |
| **Annotierte Dokumente** | Implementiert | ✅ `annotated_document_service.py`; `GET /cases/{id}/annotated-documents` (Liste), `GET /cases/{id}/annotated-documents/{document_id}` (DOCX-Download); Frontend `AnnotatedDocumentsView` mit `caseId`, echte API. |
| **Audit-Log / Activities** | Implementiert | ✅ Tabelle `activity_log` in `models/db.py`; Run-Checks und PATCH Finding schreiben Events; `GET /cases/{id}/activities` in `cases.py`; Frontend nutzt `getCaseActivities()`. |

### Frontend

| Komponente | Status | Verifiziert |
| :--- | :--- | :--- |
| **Cases-Liste** | Echte API | ✅ `cases-page.tsx` nutzt `getCases()` aus `api.ts` |
| **Case-Detail** | Echte API | ✅ `case-detail-page.tsx`: `getCase(caseId)`; documents/findings aus Response |
| **Neuer Vorgang** | Echte API | ✅ `new-case-dialog.tsx`: `createCase()`, `getPlaybooks()` |
| **Dokument-Upload** | Echte API | ✅ `document-upload-zone.tsx`: `uploadDocument()` |
| **Playbooks-Seite** | Echte API | ✅ `playbooks-page.tsx`: `getPlaybooks()` |
| **Playbook-Detail** | Echte API | ✅ `playbook-detail-page.tsx`: `getPlaybook(playbookId)`; bei 404 „Playbook nicht gefunden“. Bearbeiten, Archivieren, Löschen, Duplizieren an API angebunden. |
| **UI „Checks starten“** | Implementiert | ✅ Case-Detail: Run-Checks-Dialog mit Playbook-Auswahl, `runChecks()` |
| **UI Finding-Status** | Implementiert | ✅ Case-Detail: Status-Buttons, `updateFindingStatus()` |
| **Dashboard Playbooks** | Echte API | ✅ `dashboard-stats.tsx` lädt Playbooks via `getPlaybooks()`; Fallback leere Liste. |
| **Fachbereiche** | Konfiguration + API | ✅ `data/fachbereiche.yaml` (FB 01–16 + zentrale Einrichtungen); `GET /departments`; Neuer-Vorgang-Dialog nutzt `getDepartments()` mit Fallback auf Playbook-Liste. |
| **Playbook anlegen/bearbeiten** | Echte API | ✅ `new-playbook-dialog.tsx` (Create/Edit); `createPlaybook()`, `updatePlaybook()`, `deletePlaybook()` in `api.ts`; Playbooks-Seite „Neues Playbook“, Detail-Seite Bearbeiten/Archivieren/Löschen/Duplizieren. |
| **UI VVT-Normalisierung** | Echte API | ✅ `vvt-normalization-view.tsx` lädt per `getVVTNormalization(caseId, documentId)`; Anzeige Felder, Template, Fortschritt. |
| **UI Annotierte Dokumente** | Echte API | ✅ `annotated-documents-view.tsx` mit `caseId`; `getAnnotatedDocuments()`, `getAnnotatedDocumentBlob()`; Liste und DOCX-Download. |
| **Activity-Timeline** | Echte API | ✅ `activity-timeline.tsx` nutzt `getCaseActivities(caseId)` aus `api.ts`; Daten von `GET /cases/{id}/activities`. |

---

## 2. Priorisierte nächste Schritte (aus Roadmap + Gap)

### Schritt 1: Run-Checks-API (höchste Priorität)

- **Ziel:** Ein Endpoint führt für einen Case die Playbook-Checks aus und speichert Findings in der DB.
- **Backend:**
  - Neuer Endpoint: `POST /api/v1/cases/{case_id}/run-checks`
  - Optional: Query/Body-Parameter `playbook_id` (sonst: Case-Playbook oder Default-Playbook).
  - Ablauf: Case laden → zugehörige Dokumente mit `content` laden → Playbook laden (inkl. `content.checks` oder ähnlich) → für jedes relevante Dokument und jeden Check `check_runner.run_check(document_content, check_instruction)` aufrufen → bei Nicht-Compliance `FindingModel` anlegen und speichern (case_id, document_id, check_name, severity, description, evidence, recommendation, status=open).
  - Playbook-Format: Im Code festlegen bzw. dokumentieren (z. B. `content.checks: [{ "name": "...", "instruction": "..." }]`).
- **Dokumentation:** `docs/api.md` und `docs/roadmap.md` aktualisieren.

### Schritt 2: Frontend an echte API anbinden

- **Ziel:** Cases, Dokumente und Findings kommen aus der API, keine Mocks mehr für diese Daten.
- **Umsetzung:**
  - API-Client (z. B. `src/app/lib/api.ts`): Basis-URL aus Env, Funktionen für `GET/POST/PATCH/DELETE /cases`, `GET/POST /documents`, ggf. `GET /playbooks`.
  - **Cases:** Cases-Page: `GET /api/v1/cases`; Case-Detail: `GET /api/v1/cases/{id}` (enthält bereits documents + findings).
  - **Neuer Vorgang:** NewCaseDialog: `POST /api/v1/cases`; nach Erfolg Liste neu laden oder zur neuen Case-Detailseite navigieren.
  - **Dokumente:** Upload-Zone: `POST /api/v1/documents` (FormData: case_id, file, document_type, uploaded_by); Case-Detail: Dokumentliste aus Case-Response oder `GET /documents?case_id=...`.
  - **Findings:** Aus Case-Response (GET case) anzeigen; für Statusänderung siehe Schritt 3.
- **Playbooks:** Falls Playbooks-Seite noch Mock nutzt, auf `GET /api/v1/playbooks` umstellen.

### Schritt 3: Finding-Status (API + UI)

- **Ziel:** Status von Findings (open/accepted/overruled/fixed) änderbar und persistiert.
- **Backend:** `PATCH /api/v1/findings/{id}` mit Body `{ "status": "accepted" | "overruled" | "fixed" }` (oder Findings unter Cases-Route: `PATCH /api/v1/cases/{id}/findings/{finding_id}`).
- **Frontend:** In der Case-Detail-Seite (Findings-Liste/Detail) Dropdown oder Buttons zum Ändern des Status; nach Änderung API aufrufen und Case/Findings neu laden.

### Schritt 4: Optional – Ollama im Health-Check

- Health-Endpoint um kurzen Check gegen `OLLAMA_BASE_URL` erweitern (z. B. `/api/tags` oder `/`), nur wenn gewünscht.

### Schritt 5: Phase 2 – VVT (nach Run-Checks + Frontend-Anbindung)

- VVT-Fingerprinting (Erkennung Template-Variante).
- Kanonisches VVT-Datenmodell (Schema) + LLM-Mapping von Rohtext zu diesem Modell.
- Export Ziel-Template.
- Frontend: Anzeige normalisierter VVT (bereits Platzhalter vorhanden).

### Schritt 6: Weitere Backend-Lücken (kurzfristig sinnvoll)

- **Dokument löschen:** `DELETE /api/v1/documents/{id}` (Löschen in DB + Storage).
- **Playbook:** PATCH/DELETE für Playbooks ergänzen, falls benötigt.

---

## 3. Abgleich Roadmap/Gap ↔ Code

- **Phase 1 „Noch offen“:**  
  - Frontend an echte API anbinden: **erledigt** (Cases, Documents, Findings, Playbooks, Run-Checks, Finding-Status, Playbook-Detail nutzen `api.ts`).  
  - Dokument-Versionierung v1/v2: **erledigt** (Version pro (case_id, document_type) in `documents.py`; `_next_version_for_type()`; Frontend zeigt Version und Hinweis „Neue Version“).  
  - Asynchrone Jobs (Redis/Celery): **erledigt** (Celery-Worker in docker-compose; Task `extract_document_text`; Upload 201 sofort; `GET /cases/{id}/run-checks/status`).

- **Phase 2:**  
  - Run-Checks API: **implementiert** (`POST /cases/{id}/run-checks`, Findings persistiert).  
  - Ollama-Status: **implementiert** (`/health` prüft Ollama bei `ollama_enabled`).  
  - VVT (Fingerprinting, Modell, Mapping, Frontend): **implementiert** (`vvt_service.py`, `GET /cases/{id}/vvt-normalization`, `VVTNormalizationView`). Export Ziel-Template (DOCX) und CSV: **erledigt.**

- **Phase 3 (Cross-Document & Artefakte):**  
  - Cross-Document-Checks: **erledigt** (`scope: case`/`cross_document`, `run_cross_document_check`, Findings mit `document_id=null`, Frontend „Vorgangsbezogen“).  
  - DSB-Report, annotierte DOCX/PDF, VVT-Export: **erledigt.**  
  - Reproduzierbarkeit (playbook_version, model im activity_log): **erledigt.**

- **Gap „Findings maschinenlesbar“ / „Finding-Status in UI“:** **erledigt.**

- **Verbleibende Lücken (Roadmap Phase 4 / Gap):** AuthN/AuthZ (OAuth2/OIDC, RBAC), OCR (gescannte PDFs), DE/EN-Ausbau (sprachabhängige Playbook-Checks), optional Retention/Archivierung, Logging/Monitoring.

---

## 4. Empfohlene Reihenfolge

1. **Run-Checks-API** implementieren (Backend) + Playbook-Format für Checks festlegen.  
2. **Frontend auf echte API umstellen** (Cases, Documents, ggf. Playbooks); Run-Checks-Button in Case-Detail einbauen.  
3. **Finding-Status:** PATCH Findings + UI.  
4. Optional: Ollama Health, DELETE Document, Playbook PATCH/DELETE.  
5. Danach: **VVT** (Fingerprinting, Modell, Mapping, Export) und Phase 3 (Cross-Document, DSB-Report, kommentierte Dokumente).

Diese Reihenfolge schließt die wichtigsten Lücken aus der Gap-Analyse und bringt die Roadmap Phase 2 (Playbooks & VVT) einen konkreten Schritt voran.
