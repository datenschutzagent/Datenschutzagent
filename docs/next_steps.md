# Nächste Schritte – Plan nach Roadmap & Gap-Analyse

Stand: Feb 2026, nach Abgleich mit Code. Phase 1–3 der Roadmap und die priorisierten Gap-Punkte (Run-Checks, Frontend-API, Finding-Status, VVT, Cross-Document, Artefakte, Versionierung, Audit, Celery, OCR, Weaviate/RAG, Code-Review, DE/EN-Ausbau, **AuthN OAuth2/OIDC**) sind umgesetzt. **Verbleibende Lücken:** AuthZ/RBAC (Rollen), optional Retention/Archivierung. **Nächster Sprint:** siehe `docs/sprint_plan.md`.

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

## 2. Verbleibende Lücken & nächster Sprint

| Lücke | Priorität | Anmerkung |
| :--- | :--- | :--- |
| **AuthZ / RBAC** | Phase 4 | Rollen (z. B. viewer/editor/admin), Rechte pro Ressource; optional. |
| **Retention/Archivierung** | Optional | Konfigurierbare Aufbewahrungsfristen (Roadmap Phase 4). |

Konkrete Sprint-Planung und Backlog: **`docs/sprint_plan.md`**.

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

- **Verbleibende Lücken (Roadmap Phase 4 / Gap):** AuthZ/RBAC (Rollen), optional Retention/Archivierung, Logging/Monitoring. AuthN (OIDC), DE/EN-Ausbau, OCR und Phase 2/3 sind erledigt.
