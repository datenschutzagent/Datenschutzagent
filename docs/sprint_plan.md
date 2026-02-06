# Sprint-Plan (aktuell)

Stand: Nach Umsetzung Sprint „Asynchrone Jobs (Celery + Redis)“. Abgeschlossen: Dokument-Versionierung; Asynchrone Jobs. Vorherige Sprints (Dokumente beim Anlegen; Reproduzierbarkeit + Artefakte; Cross-Document-Checks; Fachbereiche, Playbook-YAML, Playbook-CRUD; Audit-Log + Activity-Timeline; Playbook-Detail; Mehrfach-Upload; Annotated Documents) abgeschlossen.

---

## Aktueller Sprint – Dokument-Versionierung (abgeschlossen)

1. **Datenmodell & API** – Version pro (case_id, document_type): Beim Upload wird die nächste Versionsnummer (v1, v2, …) automatisch vergeben. `GET /documents` unterstützt optional `document_type`; Sortierung nach Typ und Version.
2. **Backend** – `_next_version_for_type()` in `documents.py`; Einzel- und Bulk-Upload setzen Version automatisch. Case-Response: Dokumente sortiert nach (type, version).
3. **Frontend** – Case-Detail zeigt pro Dokument Typ-Label und Version (z. B. „VVT v2“). Upload-Dialog: Hinweis, dass Wahl eines bestehenden Dokumenttyps eine neue Version anlegt.
4. **Dokumentation** – sprint_plan.md, roadmap.md, requirements_gap.md, api.md aktualisiert.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Datenmodell & API Versionierung (case_id, document_type) | ✅ |
| 2 | Backend-Endpoints (Upload Version, GET document_type, Sortierung) | ✅ |
| 3 | Frontend: Versionen anzeigen & Hinweis „Neue Version“ | ✅ |
| 4 | Doku (sprint_plan, roadmap, requirements_gap, api) | ✅ |

---

## Vorheriger Sprint – Dokumente beim Anlegen (optional) (abgeschlossen)

1. **Neuer Vorgang Dialog** – Optionaler dritter Schritt „Dokumente (optional)“ im Dialog; Nutzer können Dateien auswählen und einen Dokumenttyp für alle setzen. Nach `createCase()` wird bei vorhandenen Dateien `uploadDocumentsBulk(newCase.id, files, documentType, assignee)` aufgerufen; danach Navigation zur Case-Detailseite (bestehender `onSuccess`-Flow).
2. **Dokumentation** – sprint_plan.md, roadmap.md, requirements_gap.md um den neuen Flow ergänzt.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Optionaler Schritt „Dokumente“ im Neuer-Vorgang-Dialog (Frontend) | ✅ |
| 2 | Doku (sprint_plan, roadmap, requirements_gap) | ✅ |

---

## Vorheriger Sprint – Reproduzierbarkeit + optionale Artefakte (abgeschlossen)

1. **Reproduzierbarkeit** – Bei `run_checks` im `activity_log.payload`: `playbook_version` (aus Playbook) und `model` (aus `settings.ollama_model`) ergänzt; Doku (api.md, requirements_gap.md) angepasst.
2. **finding_status_updated** – Payload unverändert (Playbook-Kontext am Finding nicht gespeichert; bewusst weggelassen).
3. **VVT Ziel-Template (DOCX)** – `GET /cases/{id}/vvt-normalization/export?format=docx`; DOCX mit Dokumentname, erkanntem Template und Tabelle der normalisierten VVT-Felder.
4. **PDF annotierte Dokumente** – `build_annotated_pdf()` in `annotated_document_service.py`; Download via `GET /cases/{id}/annotated-documents/{document_id}?format=pdf`.
5. **Dokumentation** – roadmap.md, requirements_gap.md, sprint_plan.md, api.md aktualisiert.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Reproduzierbarkeit (playbook_version + model im Payload) | ✅ |
| 2 | finding_status_updated (Kontext optional) | ✅ |
| 3 | VVT Export format=docx | ✅ |
| 4 | PDF annotierte Dokumente | ✅ |
| 5 | Doku | ✅ |

---

## Vorheriger Sprint – Cross-Document-Checks (abgeschlossen)

1. **Playbook-Format** – Checks unterstützen optional `scope` (oder `type`): `document` (Standard) vs. `case`/`cross_document`. YAML-Import in `playbook_import.py` setzt Default `document`, falls nicht angegeben.
2. **Check Runner** – `run_cross_document_check(documents: list[(UUID, str)], check_instruction)` in `check_runner.py`; Multi-Dokument-Prompt mit Truncation pro Dokument.
3. **Run-Checks** – In `cases.py`: Aufteilung in Document-Checks (pro Dokument) und Case-Checks (ein Lauf über alle Dokumente); Case-Findings mit `document_id=None`.
4. **Frontend** – Findings mit `document_id=null` werden als „Vorgangsbezogen“ (Badge) bzw. im Dialog als „Vorgangsbezogen (Cross-Document)“ angezeigt.
5. **Doku** – api.md, roadmap.md, requirements_gap.md, sprint_plan.md aktualisiert.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Playbook scope/type + Import | ✅ |
| 2 | run_cross_document_check | ✅ |
| 3 | Run-Checks: document vs. case | ✅ |
| 4 | Frontend Vorgangsbezogen | ✅ |
| 5 | Doku | ✅ |

---

## Vorheriger Sprint – Fachbereiche, Playbook-YAML, Playbook-CRUD (abgeschlossen)

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

## Sprint – Asynchrone Jobs (Celery + Redis) (abgeschlossen)

**Ziel:** Lange laufende Extraktion blockiert nicht mehr den HTTP-Request; bessere UX bei großen Dateien.

1. **Backend – Celery & Redis** – Celery-App an Redis; Worker-Service in docker-compose; Konfiguration `CELERY_BROKER_URL`, `celery_enabled`; Fallback: bei fehlendem Broker synchrone Extraktion.
2. **Backend – Task Dokument-Extraktion** – Task `extract_document_text`; Upload speichert Datei und erstellt Dokument mit `content=None`, sendet Task; Worker liest Datei, extrahiert Text, aktualisiert `Document.content`. Einzel- und Bulk-Upload geben sofort 201.
3. **Backend – Run-Checks-Status** – `GET /cases/{id}/run-checks/status` liefert letzten run_checks-Activity-Eintrag (für Polling); Run-Checks selbst weiterhin synchron ausgeführt.
4. **Frontend** – Unverändert (Backend async; optional später Polling für Extraktion).
5. **Dokumentation** – sprint_plan.md, roadmap.md, requirements_gap.md, api.md aktualisiert.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Celery-App + Redis; Worker in docker-compose | ✅ |
| 2 | Task Dokument-Extraktion; Upload → async Extraktion | ✅ |
| 3 | Optional: Task Run-Checks + Status/Polling-API | ✅ (Status-Endpoint) |
| 4 | Optional: Frontend Status/Polling für Upload bzw. Run-Checks | ✅ (unverändert) |
| 5 | Doku (sprint_plan, roadmap, requirements_gap, api) | ✅ |

---

## Folgesprint (optional, danach)

- OCR (gescannte PDFs), DE/EN-Ausbau, AuthN/AuthZ.
