# Requirements Gap Analysis

Abgleich der Projektbeschreibung (Anforderungen) mit dem aktuellen Implementierungsstand. Stand: nach Code-Review-Umsetzung (Feb 2026).

---

## 1. Funktionale Anforderungen

### A) Vorgangsverwaltung (Case Management)

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Vorgang anlegen mit Metadaten | ✅ | Backend + Frontend; API Create/Update. Optional: Dokumente bereits im Dialog „Neuer Vorgang“ hochladbar (Frontend-Flow: nach Create sofort `uploadDocumentsBulk`). |
| Mehrere Dokumente je Vorgang | ✅ | Einzelupload + Mehrfach-Upload: `POST /api/v1/documents/bulk` (mehrere Dateien, gleicher Typ); Frontend nutzt Bulk bei gleichem Dokumenttyp. Optional: Dokumente im Dialog „Neuer Vorgang“ (Schritt 3) auswählbar. |
| Versionierung (Stände je Dokument) | ✅ | Version pro (case_id, document_type) beim Upload automatisch (v1, v2, …); `GET /documents?document_type=…`; Frontend zeigt Version (z. B. VVT v2) und Hinweis „Neue Version“ im Upload-Dialog. |
| Statusmodell | ✅ | `CaseStatusEnum`; Status im Case-Modell. |
| Vorgang löschen | ✅ | `DELETE /api/v1/cases/{id}`. |

### B) Dokumentverarbeitung

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Formate DOCX, PDF, XLSX | ✅ | `document_processor.py` (PyMuPDF, python-docx, openpyxl). |
| Text- und Strukturextraktion | ✅ | Bei Upload; Speicherung in `Document.content`. |
| OCR (gescannte PDFs) | ✅ | Ollama Vision (z. B. qwen2.5-vl, minicpm-v); bei textarmen PDFs automatischer Fallback in `document_processor.py`; `extraction_method` (text/ocr) am Document, Frontend-Badge „Text per OCR extrahiert“. |
| DE/EN | ✅ | Case hat `language` (de, en, de_en). Run-Checks und VVT-Normalisierung erhalten die Case-Sprache; LLM-Prompts enthalten Sprachhinweis. Playbook-Checks unterstützen optional `instruction_en` für englische Anforderungen. |

### C) Playbook-basierte Vorprüfung

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Playbooks im System, versioniert | ✅ | `Playbook`-Modell (JSONB), CRUD unter `/api/v1/playbooks/`. |
| Dokument-Checks | ✅ | `check_runner.run_check()` mit PydanticAI/Ollama; strukturiertes Ergebnis. |
| Vorgangs-/Cross-Document-Checks | ✅ | Playbook-Checks mit `scope: case`/`cross_document`; `run_cross_document_check()`; Findings mit `document_id=null`; Frontend „Vorgangsbezogen“. |
| Check-Lauf pro Case + persistente Findings | ✅ | `POST /api/v1/cases/{id}/run-checks`; Check Runner wird aufgerufen, Findings in DB gespeichert. |

### D) VVT-Normalisierung

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Template-Fingerprinting | ✅ | Im VVT-Service (LLM); `source_template` in `GET /cases/{id}/vvt-normalization`. |
| Kanonisches VVT-Datenmodell | ✅ | Pydantic-Schema (`VVTFieldResponse`, `VVTNormalizationResponse`); LLM-Mapping in `vvt_service.py`. |
| Export (CSV / Ziel-Template) | ✅ | CSV-Export: `GET /cases/{id}/vvt-normalization/export`; Ziel-Template DOCX: `?format=docx`. |

### E) Artefakte / Output

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| DSB Summary Report | ✅ | `dsb_report_service.py`, `GET /api/v1/cases/{id}/dsb-report` (format=json \| markdown); Frontend DSBReportView. Header-Button „DSB-Report“ startet Markdown-Download direkt. |
| Kommentierte Dokumente (DOCX/PDF) | ✅ | DOCX: `GET /cases/{id}/annotated-documents/{document_id}` (Standard). PDF: `?format=pdf`. Frontend: AnnotatedDocumentsView. Header-Button „Kommentierte Dokumente“ wechselt in den Tab „Annotierte Dokumente“. |
| Findings maschinenlesbar (JSON) | ✅ | Finding-Modell, Case-Response inkl. Findings, Erzeugung via Run-Checks; PATCH `/api/v1/findings/{id}` für Status. |

### F) Auditierbarkeit

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Logging Playbook-/Modell-Version, Check-Läufe | ✅ | Tabelle `activity_log` (case_id, event_type, payload, created_at); Events `run_checks`, `finding_status_updated`; `GET /api/v1/cases/{id}/activities`; Frontend Activity-Timeline nutzt echte API. Bei fehlgeschlagenen/übersprungenen Checks: Payload enthält `errors` und `skipped_checks_count`; Backend loggt Exceptions. |
| Finding-Status accepted/overruled/fixed | ✅ | Enum und DB-Felder; `PATCH /api/v1/findings/{id}`; UI in Case-Detail (Status-Buttons) implementiert. |

---

## 2. Nicht-funktionale Anforderungen

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| On-Prem / datenschutzkonform (LLM lokal) | ✅ | Ollama; Konfiguration über `OLLAMA_*`. |
| Storage (lokal + MinIO) | ✅ | `storage.py`: Backends umschaltbar. |
| AuthN/AuthZ, Rollen | ❌ | Nicht implementiert. |
| Retention/Archivierung konfigurierbar | ❌ | Nicht implementiert. |
| Reproduzierbarkeit (Playbook-/Modellversion) | ✅ | Bei jedem `run_checks`-Event werden `playbook_version` und `model` (Ollama) im `activity_log.payload` geloggt; Reproduktion von Check-Läufen nachvollziehbar. |
| Tests & CI | ✅ | Backend: pytest (backend/tests/), Frontend: Vitest + Testing Library (npm run test). CI: GitHub Actions (Frontend- und Backend-Tests mit Postgres-Service). |
| Dokumentation & Betrieb | ✅ | README mit Schnellstart, Docker, Tests, Migrations-Hinweis; Migrations-Strategie (manuelle SQL-Skripte unter backend/migrations/) dokumentiert. |

---

## 3. Priorisierte Schritte (Gap-Schließung)

1. ~~**Run-Checks-API**~~ ✅ Erledigt. ~~**Frontend**~~ ✅ Erledigt (Cases, Documents, Findings, Playbooks, Run-Checks, Finding-Status, **Playbook-Detail** nutzen echte API). ~~**Activity-Timeline** nutzt weiterhin Mock~~ ✅ Erledigt (Audit-Log + `GET /cases/{id}/activities`, Activity-Timeline an API).
2. ~~**VVT:** Fingerprinting, kanonisches Modell, Mapping, Frontend-Ansicht~~ ✅ Erledigt. ~~**Export Ziel-Template (DOCX)**~~ ✅ (`GET /cases/{id}/vvt-normalization/export?format=docx`).
3. ~~**Vorgangs-/Cross-Document-Checks**~~ ✅ Erledigt (Playbook `scope: case`/`cross_document`, `run_cross_document_check`, Findings mit `document_id=null`, Frontend „Vorgangsbezogen“).
4. **Artefakte:** ~~DSB-Report~~ ✅, ~~kommentierte DOCX~~ ✅, ~~PDF-Export~~ ✅ (`?format=pdf` bei annotated-documents Download).
5. **Dokument-Versionierung:** ~~v1/v2 pro Dokumenttyp~~ ✅ (Version pro (case_id, document_type) beim Upload; GET /documents?document_type=…; Frontend Version + Hinweis).
6. **Sicherheit & Audit:** ~~Audit-Log~~ ✅ (activity_log, Activities-API, Timeline). AuthN/AuthZ noch offen.
7. ~~**Asynchrone Jobs (Celery + Redis)**~~ ✅ Extraktion nach Upload asynchron (Task `extract_document_text`); Upload 201 sofort. Run-Checks-Status: `GET /cases/{id}/run-checks/status`. Siehe sprint_plan.md.
8. ~~**OCR (gescannte PDFs)**~~ ✅ Ollama Vision (qwen2.5-vl / minicpm-v); Schwellwert in `document_processor.py`; `extraction_method` am Document; Frontend-Badge „Text per OCR extrahiert“.
9. **Weaviate / RAG (optionale zweite Prüfvariante):** ✅ Dokumente werden nach Extraktion in Chunks in Weaviate indexiert (Ollama Embedding). Run-Checks unterstützt Strategien `full_text` und `rag`; beide parallel für Vergleich. Findings mit `source_strategy`; Frontend Badge und Dialog-Auswahl (Volltext / RAG / Beide). Konfiguration: `WEAVIATE_INDEXING_ENABLED`, `WEAVIATE_URL`, Chunk-/Top-K-Parameter.
10. **Code-Review-Umsetzung (Feb 2026):** ✅ Run-Checks: Fehler loggen und im Activity-Payload (`errors`, `skipped_checks_count`) zurückmelden. Case-Delete: Weaviate-Chunk-Löschung nicht blockierend (`asyncio.to_thread`). Frontend: DSB-Report- und „Kommentierte Dokumente“-Buttons funktional; Frist mit aktuellem Datum. Case-Detail in Tab-Komponenten aufgeteilt; API `parseErrorResponse()`. Repo: Stray-Datei entfernt, requirements gepinnt. Tests (pytest, Vitest) und CI (GitHub Actions); README und Migrations-Strategie ergänzt.
