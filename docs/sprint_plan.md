# Sprint-Plan (aktuell)

Stand: Sprint **Code-Review / Verbesserungen** abgeschlossen (Feb 2026). Zuvor: Weaviate/RAG, OCR, Celery, Dokument-Versionierung, Cross-Document, Artefakte, Audit, Playbook-CRUD, Annotated Documents.

---

## Sprint – Code-Review / Verbesserungen (abgeschlossen, Feb 2026)

1. **Run-Checks Fehlersichtbarkeit** – Exceptions bei Check-Läufen werden geloggt; im Activity-Payload erscheinen bei Fehlern `errors` (Liste mit check, scope, document_id, strategy, error) und `skipped_checks_count`.
2. **Case-Delete / Weaviate** – `delete_chunks_by_case_id` wird in `asyncio.to_thread` ausgeführt (nicht blockierend).
3. **Frontend Case-Detail** – DSB-Report-Button startet Markdown-Download; Button „Kommentierte Dokumente“ wechselt in Tab „Annotierte Dokumente“. Fristberechnung mit aktuellem Datum (kein Hardcoding).
4. **Frontend Struktur** – Case-Detail in Tab-Komponenten aufgeteilt (CaseOverviewTab, CaseDocumentsTab, CaseFindingsTab); API-Fehlerbehandlung zentral in `parseErrorResponse()`.
5. **Repo** – Stray-Datei entfernt; `.gitignore` für pip-Artefakte; `backend/requirements.txt` mit gepinnten Versionen.
6. **Tests** – Backend: pytest, pytest-asyncio, httpx; Tests unter `backend/tests/` (Health, Departments, Cases). Frontend: Vitest, Testing Library; Tests z. B. für `parseErrorResponse`.
7. **Doku & CI** – README erweitert (Schnellstart, Docker, Tests, Migrations-Hinweis). GitHub Actions: Frontend- und Backend-Tests (Backend mit Postgres-Service). Migrations-Strategie in README dokumentiert.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Run-Checks: Fehler loggen + Activity-Payload errors/skipped_checks_count | ✅ |
| 2 | delete_chunks_by_case_id nicht blockierend (asyncio.to_thread) | ✅ |
| 3 | Frontend: DSB-Report- und Kommentierte-Dokumente-Buttons; Frist-Datum | ✅ |
| 4 | Case-Detail Tab-Komponenten; parseErrorResponse in api.ts | ✅ |
| 5 | Repo: Stray-Datei, .gitignore, requirements pinnen | ✅ |
| 6 | pytest Backend, Vitest Frontend | ✅ |
| 7 | README, Migrations-Doku, CI (GitHub Actions) | ✅ |

---

## Vorheriger Sprint – Weaviate / RAG (abgeschlossen)

1. **Weaviate + Chunking** – Weaviate-Container in docker-compose (Vectorizer none); Konfiguration `WEAVIATE_URL`, `WEAVIATE_INDEXING_ENABLED`, Chunk-Größe/Overlap, `WEAVIATE_TOP_K`, `OLLAMA_EMBEDDING_MODEL`. Service `weaviate_service.py`: Chunking, Embedding via Ollama, Schema DocumentChunk, Indexierung und Abruf (get_relevant_chunks, get_relevant_chunks_for_case).
2. **Indexierung an Extraktion** – Nach Celery-Task `extract_document_text` bei aktivierter Weaviate-Indexierung Chunks indexieren. Bei DELETE Dokument bzw. DELETE Case Chunks in Weaviate entfernen.
3. **RAG-Check-Runner** – `run_check_rag(document_id, case_id, instruction)` und `run_cross_document_check_rag(case_id, instruction)` in check_runner.py; Abruf relevanter Chunks, Kontext an LLM, gleiches CheckResult-Schema.
4. **Run-Checks erweitern** – Body-Parameter `strategies`: `["full_text"]`, `["rag"]` oder `["full_text", "rag"]`. Beide Varianten parallel ausführbar; Findings mit `source_strategy` (full_text | rag). Bei RAG nicht verfügbar: weicher Fallback, Hinweis im Activity-Payload.
5. **Finding-Modell & Frontend** – Migration `002_add_finding_source_strategy.sql`; FindingResponse und API mit `source_strategy`. Frontend: Badge „Volltext“/„RAG“ pro Finding; Run-Checks-Dialog mit Auswahl „Volltext“, „RAG“, „Beide (Vergleich)“.
6. **Dokumentation** – roadmap.md, architecture.md, api.md, sprint_plan.md, requirements_gap.md um Weaviate, Chunking, RAG-Variante und Parallel-Betrieb ergänzt.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Weaviate + Chunking (docker-compose, Schema, Embedding, Index-Service) | ✅ |
| 2 | Indexierung an Extraktion (Celery) + Delete-Hooks (Dokument/Case) | ✅ |
| 3 | RAG-Check-Runner (run_check_rag, run_cross_document_check_rag) | ✅ |
| 4 | Run-Checks strategies + source_strategy an Findings | ✅ |
| 5 | Finding source_strategy + Frontend Badge + Run-Checks-Dialog | ✅ |
| 6 | Doku (roadmap, architecture, api, sprint_plan, requirements_gap) | ✅ |

---

## Vorheriger Sprint – Dokument-Versionierung (abgeschlossen)

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

## Sprint – OCR (gescannte PDFs) via Ollama Vision (abgeschlossen)

**Ziel:** Gescannte PDFs (ohne Text-Layer) werden per OCR mit Ollama-Vision-Modellen (z. B. Qwen2.5-VL, MiniCPM-V) verarbeitet; Run-Checks und VVT-Normalisierung funktionieren auch für eingescannte Dokumente. Kennzeichnung „Text per OCR extrahiert“ im Frontend.

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | **Backend – OCR-Pipeline** – In `document_processor.py`: Für PDFs Schwellwert (Zeichen pro Seite); bei Textarmut: PDF-Seiten mit PyMuPDF als PNG rendern, Ollama Vision (`ollama_ocr_model`) pro Seite, Text zusammenfügen. Konfiguration: `ollama_ocr_model`, `ollama_ocr_enabled`, `ocr_min_chars_per_page`, `ocr_dpi`. | ✅ |
| 2 | **Dependencies** – Kein Tesseract/poppler; bestehende `ollama`-Bibliothek und PyMuPDF (PNG-Rendering) genutzt. | ✅ |
| 3 | **ExtractionResult & Celery** – `extract_text` liefert `ExtractionResult(text, extraction_method)`; Celery-Task schreibt `content` und `extraction_method` (text/ocr). | ✅ |
| 4 | **Datenmodell & API** – Document um `extraction_method` erweitert; Migration `backend/migrations/001_add_document_extraction_method.sql`; Document-Response und Case-Response liefern das Feld. | ✅ |
| 5 | **Frontend** – Case-Detail: Bei Dokumenten mit `extraction_method === "ocr"` Badge „Text per OCR extrahiert“. | ✅ |
| 6 | **Dokumentation** – roadmap.md, requirements_gap.md, api.md, sprint_plan.md aktualisiert. | ✅ |

---

## Folgesprints (optional, danach)

- **DE/EN-Ausbau:** Case-Sprache (`language`) in Playbook-Checks und VVT-Prompts berücksichtigen; ggf. getrennte Check-Texte pro Sprache.
- **AuthN/AuthZ:** OAuth2/OIDC (z. B. Keycloak), RBAC (Rollen), geschützte API-Routen und Frontend-Login.
- **Retention/Archivierung:** Konfigurierbare Aufbewahrungsfristen (Roadmap Phase 4).
