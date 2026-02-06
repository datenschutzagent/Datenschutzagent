# Development Roadmap

Überblick über den Weg vom aktuellen Stand zum MVP und darüber hinaus (basierend auf der Projektbeschreibung).

---

## Code-Qualität & Betrieb (abgeschlossen, Feb 2026)

Nach Abschluss von Weaviate/RAG wurden Verbesserungen aus einem systematischen Code-Review umgesetzt:

| Bereich | Status | Details |
| :--- | :--- | :--- |
| Run-Checks Fehlersichtbarkeit | ✅ | Exceptions bei Check-Läufen werden geloggt; im Activity-Payload erscheinen bei Fehlern `errors` (Liste mit check, scope, strategy, error) und `skipped_checks_count`. |
| Case-Delete / Weaviate | ✅ | `delete_chunks_by_case_id` wird nicht blockierend in `asyncio.to_thread` ausgeführt. |
| Frontend Case-Detail | ✅ | DSB-Report-Button startet Markdown-Download; „Kommentierte Dokumente“ wechselt in den Tab „Annotierte Dokumente“. Fristberechnung nutzt aktuelles Datum (kein Hardcoding). |
| Frontend Struktur | ✅ | Case-Detail in Tab-Komponenten aufgeteilt (CaseOverviewTab, CaseDocumentsTab, CaseFindingsTab); API-Fehlerbehandlung zentral in `parseErrorResponse()`. |
| Repo & Abhängigkeiten | ✅ | Stray-Datei entfernt; `.gitignore` für pip-Artefakte; `backend/requirements.txt` mit gepinnten Versionen. |
| Tests | ✅ | Backend: pytest + pytest-asyncio + httpx, Tests unter `backend/tests/` (Health, Departments, Cases). Frontend: Vitest + Testing Library, Tests z. B. für `parseErrorResponse`. |
| Doku & CI | ✅ | README erweitert (Schnellstart, Docker, Tests, Migrations-Hinweis). GitHub Actions: Frontend-Tests (npm test), Backend-Tests (Postgres-Service, pytest). Migrations-Strategie in README dokumentiert (SQL-Skripte manuell, kein Auto-Run). |

---

## Phase 1: Fundament (abgeschlossen)

**Ziel:** Case-Verwaltung, Dokumenten-Upload und -Speicherung, Textextraktion.

| Bereich | Status | Details |
| :--- | :--- | :--- |
| Projekt-Setup | ✅ | Docker Compose: Postgres, MinIO, Redis, Backend, Frontend. |
| Datenmodelle | ✅ | `Case`, `Document` (inkl. `content`), `Finding`, `Playbook`. |
| Case-API | ✅ | CRUD inkl. `DELETE /api/v1/cases/{id}`. Optional: Dokumente bereits im Dialog „Neuer Vorgang“ hochladbar (Frontend-Flow: Create Case → Upload Bulk). |
| Storage | ✅ | Lokal und MinIO in `backend/app/storage.py`. |
| Dokumenten-Upload | ✅ | Einzelupload + Mehrfach-Upload (`POST /documents/bulk`); Extraktion bei Upload (PDF/DOCX/XLSX). Optional: Dokumente im Dialog „Neuer Vorgang“ (Schritt 3) auswählbar, Upload nach Case-Erstellung. |
| Textextraktion | ✅ | `document_processor.py`; Ergebnis in `Document.content`. **OCR** für gescannte PDFs: Ollama Vision (z. B. Qwen2.5-VL); bei textarmen PDFs automatischer Fallback; `extraction_method` (text/ocr) in Document und Frontend-Badge. |
| Playbook-API | ✅ | CRUD Playbooks (`/api/v1/playbooks/`). |
| LLM / Check Runner | ✅ | PydanticAI + Ollama (`core/llm.py`), `check_runner.run_check()`. |

**Noch offen (Phase 1):**
- ~~Frontend an echte API angebunden~~ ✅ Erledigt (Cases, Dokumente, Findings, Playbooks, Run-Checks, Finding-Status, **Playbook-Detail** nutzen `api.ts`).
- ~~**Activity-Timeline:** nutzt Mock-Daten bis ein Audit-Log/Activities-API existiert~~ ✅ Erledigt: Audit-Log (`activity_log`), `GET /cases/{id}/activities`; Frontend Activity-Timeline nutzt echte API.
- ~~Dokument-Versionierung: v1/v2 pro Dokumenttyp noch offen~~ ✅ Erledigt: Version pro (case_id, document_type) beim Upload automatisch (v1, v2, …); `GET /documents?document_type=…`; Sortierung nach Typ, Version; Frontend zeigt Version und Hinweis bei Upload.
- ~~Asynchrone Jobs: Redis/Celery noch nicht genutzt; Extraktion synchron~~ ✅ Celery + Redis; Worker in docker-compose; Task `extract_document_text`; Upload gibt sofort 201, Extraktion asynchron. Bei fehlendem Broker synchrone Extraktion. `GET /cases/{id}/run-checks/status` für Polling.
- ~~OCR (gescannte PDFs)~~ ✅ Ollama Vision (qwen2.5-vl / minicpm-v); Schwellwert `ocr_min_chars_per_page`; `extraction_method` am Document; Frontend-Badge „Text per OCR extrahiert“.

---

## Phase 2: Playbooks & VVT (abgeschlossen)

**Ziel:** Playbook-Checks pro Vorgang ausführen, VVT normalisieren.

| Bereich | Status | Details |
| :--- | :--- | :--- |
| Run-Checks API | ✅ | `POST /api/v1/cases/{id}/run-checks` (Body: `playbook_id`, optional `strategies`); Findings werden persistiert. |
| Ollama-Status | ✅ | `/health` prüft bei `ollama_enabled` die Erreichbarkeit (GET Ollama `/api/tags`); bei Fehler `status: degraded`. |
| VVT-Fingerprinting | ✅ | Template-Erkennung im VVT-Service (LLM); `source_template` in Response. |
| Kanonisches VVT-Modell | ✅ | Schema in `schemas.py`; `vvt_service.py` mit LLM-Mapping Rohtext → kanonische Felder. |
| Frontend Checks/VVT | ✅ | Run-Checks-Button (Volltext/RAG/Beide), Finding-Status; VVT-Tab nutzt `GET /cases/{id}/vvt-normalization`, echte API. |

**Phase 2 – alle Schritte erledigt:** Run-Checks-API, Ollama Health, VVT (Fingerprinting, Modell, Mapping, Frontend), CSV-Export, Ziel-Template (DOCX).

---

## Phase 3: Cross-Document & Artefakte

**Ziel:** Konsistenzprüfungen über Dokumente hinweg, DSB-Reports, kommentierte Rückgabedokumente.

- **Consistency Engine:** ✅ Multi-Dokument-Kontext für LLM; Playbook-Checks mit `scope: case`/`cross_document`; `run_cross_document_check()` in `check_runner.py`; Findings mit `document_id=null`; Frontend kennzeichnet „Vorgangsbezogen“.
- **Artefakte:** DSB Summary Report (Markdown/JSON) ✅ (`GET /cases/{id}/dsb-report`); kommentierte DOCX ✅ (`GET /cases/{id}/annotated-documents`, Download); kommentierte PDF ✅ (`?format=pdf`).
- **VVT-Export:** CSV ✅ (`GET /cases/{id}/vvt-normalization/export`); Ziel-Template (DOCX) ✅ (`?format=docx`).
- **Feedback:** Finding-Status (Accepted/Overruled/Fixed) in UI; Audit bei Statusänderungen ✅ (activity_log-Einträge bei Finding-Status-Update).
- **Reproduzierbarkeit:** Bei jedem `run_checks`-Event werden `playbook_version` und `model` (Ollama) im `activity_log.payload` geloggt ✅. Bei fehlgeschlagenen oder übersprungenen Checks zusätzlich `errors` (Liste mit check, scope, strategy, error) und `skipped_checks_count` ✅.
- **Weaviate / RAG (optional):** ✅ Vektordatenbank Weaviate (Docker); Dokumente werden nach Textextraktion in Chunks zerlegt, per Ollama eingebettet und in Weaviate indexiert. Run-Checks unterstützt die Strategien `full_text` (bestehend) und `rag` (Abruf relevanter Chunks, Prüfung nur auf diesem Kontext). Beide Strategien können parallel ausgeführt werden (Vergleich/Validierung). Findings tragen `source_strategy` (`full_text` \| `rag`). Indexierung konfigurierbar (`WEAVIATE_INDEXING_ENABLED`, `WEAVIATE_URL`); bei Dokument-/Case-Löschung werden Chunks in Weaviate entfernt (nicht blockierend via `asyncio.to_thread`).
- **DE/EN-Ausbau:** ✅ Case-Sprache (`language`: de, en, de_en) wird an Run-Checks (Check Runner) und VVT-Normalisierung durchgereicht. LLM-Prompts enthalten einen Sprachhinweis („Evaluate and respond in German/English“); VVT-Feldwerte und Findings können sprachangepasst sein. Playbook-Checks unterstützen optional `instruction_en`; bei Case-Sprache en/de_en wird diese verwendet.

---

## Phase 4: Produktionsreife

**Ziel:** Sicherheit, Skalierung, Nachvollziehbarkeit.

- **Sicherheit:** Authentifizierung (OAuth2/OIDC) ✅ – Optional aktivierbar (`OIDC_ENABLED=true`). JWT-Validierung via JWKS (Issuer Discovery); Nutzer aus Token (`sub`), bei erstem Login in Tabelle `users` angelegt (`oidc_sub`). Geschützte Routen erfordern `Authorization: Bearer <token>`; `/health` und `GET /api/v1/auth/config` öffentlich. Frontend: Login-Redirect zu IdP, PKCE, Callback, Token in sessionStorage, Logout (optional End-Session-Redirect). **RBAC (Rollen)** ✅ – Eine Rolle pro Nutzer (`viewer`, `editor`, `admin`). Schreib-Routen nur für editor/admin; Admin-Endpoints nur für admin. GET /me liefert `role`; Frontend blendet Schreib- und Admin-Aktionen für viewer aus. Default-Rolle für neue User: `RBAC_DEFAULT_ROLE` (z. B. `viewer`).
- **Betrieb:** ~~Celery für lange Jobs~~ ✅ Dokument-Extraktion asynchron (Celery + Redis). Run-Checks weiterhin synchron; Status-Endpoint für Polling. Logging/Monitoring optional.
- **Audit:** ✅ Audit-Log (`activity_log`) für Check-Läufe und Finding-Status; Activity-Timeline an API. Payload bei `run_checks` enthält `playbook_version` und `model` (Reproduzierbarkeit). Erweiterung (z. B. unveränderlich, weitere Event-Typen) optional.

---

## Legende

| Symbol | Bedeutung |
| :--- | :--- |
| ✅ | Erledigt |
| ⚠️ | Teilweise / Nachbesserung nötig |
| ❌ | Noch nicht umgesetzt |
