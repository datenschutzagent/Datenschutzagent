# Sprint-Plan (aktuell)

Stand: Nach Umsetzung Fachbereiche, Playbook-YAML und Playbook-CRUD-Frontend. Vorherige Sprints (Audit-Log + Activity-Timeline, Playbook-Detail, Mehrfach-Upload, Annotated Documents) abgeschlossen.

---

## Letzter Sprint – Fachbereiche, Playbook-YAML, Playbook-CRUD (abgeschlossen)

1. **Fachbereiche** – `backend/app/data/fachbereiche.yaml` (FB 01–16 + zentrale Einrichtungen); `GET /api/v1/departments`; Frontend Neuer-Vorgang-Dialog bezieht Fachbereichs-Liste aus API (Fallback: Playbooks).
2. **Playbook-YAML** – Standard-Playbooks pro Fachbereich und zentrale Einrichtung in `backend/app/data/playbooks/*.yaml`; Format: name, version, department, case_type, checks.
3. **Auto-Import** – Beim ersten Start (leere Playbook-Tabelle) werden alle YAML-Playbooks importiert (`playbook_import.py`, Aufruf im Lifespan).
4. **Frontend Playbook-CRUD** – `createPlaybook`, `updatePlaybook`, `deletePlaybook` in `api.ts`; Dialog „Neues Playbook“; Playbook-Detail: Bearbeiten, Archivieren, Löschen, Duplizieren.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Fachbereiche YAML + GET /departments | ✅ |
| 2 | Playbook-YAML-Dateien (16 FB + 9 zentral) | ✅ |
| 3 | Auto-Import bei leerer Playbook-Tabelle | ✅ |
| 4 | Frontend: create/update/delete Playbook + UI | ✅ |
| 5 | Doku (architecture, api, next_steps, sprint_plan) | ✅ |

---

## Vorheriger Sprint – Audit-Log & Activity-Timeline (abgeschlossen)

1. **Audit-Log (Backend)** – Tabelle `activity_log`; Events bei Run-Checks und Finding-Status-Update.
2. **Activities-API** – `GET /api/v1/cases/{id}/activities`; Response sortiert nach Zeit.
3. **Activity-Timeline (Frontend)** – Nutzt `getCaseActivities(caseId)`; Mock entfernt.
4. **Dokumentation** – roadmap, requirements_gap, next_steps, api.md, architecture.md aktualisiert.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Audit-Events beim Run-Checks schreiben | ✅ |
| 2 | Audit-Events bei Finding-Status-Update | ✅ |
| 3 | GET /cases/{id}/activities | ✅ |
| 4 | Frontend Activity-Timeline auf API | ✅ |
| 5 | Docs aktualisieren | ✅ |

---

## Folgesprint (optional)

- Cross-Document-Checks (Multi-Dokument-Kontext im Check Runner).
- Optional: VVT Ziel-Template (DOCX), PDF annotierte Dokumente.
