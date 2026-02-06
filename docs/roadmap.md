# Development Roadmap

Überblick über den Weg vom aktuellen Stand zum MVP und darüber hinaus (basierend auf der Projektbeschreibung).

---

## Phase 1: Fundament (abgeschlossen)

**Ziel:** Case-Verwaltung, Dokumenten-Upload und -Speicherung, Textextraktion.

| Bereich | Status | Details |
| :--- | :--- | :--- |
| Projekt-Setup | ✅ | Docker Compose: Postgres, MinIO, Redis, Backend, Frontend. |
| Datenmodelle | ✅ | `Case`, `Document` (inkl. `content`), `Finding`, `Playbook`. |
| Case-API | ✅ | CRUD inkl. `DELETE /api/v1/cases/{id}`. |
| Storage | ✅ | Lokal und MinIO in `backend/app/storage.py`. |
| Dokumenten-Upload | ✅ | Einzelupload; Extraktion bei Upload (PDF/DOCX/XLSX). |
| Textextraktion | ✅ | `document_processor.py`; Ergebnis in `Document.content`. |
| Playbook-API | ✅ | CRUD Playbooks (`/api/v1/playbooks/`). |
| LLM / Check Runner | ✅ | PydanticAI + Ollama (`core/llm.py`), `check_runner.run_check()`. |

**Noch offen (Phase 1):**
- ~~Frontend an echte API angebunden~~ ✅ Erledigt (Cases, Dokumente, Findings, Playbooks, Run-Checks, Finding-Status nutzen `api.ts`).
- Dokument-Versionierung: v1/v2 pro Dokumenttyp noch offen.
- Asynchrone Jobs: Redis/Celery noch nicht genutzt; Extraktion synchron.

---

## Phase 2: Playbooks & VVT (in Arbeit)

**Ziel:** Playbook-Checks pro Vorgang ausführen, VVT normalisieren.

| Bereich | Status | Details |
| :--- | :--- | :--- |
| Run-Checks API | ✅ | `POST /api/v1/cases/{id}/run-checks` (Body: `playbook_id`); Findings werden persistiert. |
| Ollama-Status | ✅ | `/health` prüft bei `ollama_enabled` die Erreichbarkeit (GET Ollama `/api/tags`); bei Fehler `status: degraded`. |
| VVT-Fingerprinting | ✅ | Template-Erkennung im VVT-Service (LLM); `source_template` in Response. |
| Kanonisches VVT-Modell | ✅ | Schema in `schemas.py`; `vvt_service.py` mit LLM-Mapping Rohtext → kanonische Felder. |
| Frontend Checks/VVT | ✅ | Run-Checks-Button, Finding-Status; VVT-Tab nutzt `GET /cases/{id}/vvt-normalization`, echte API. |

**Nächste Schritte Phase 2:**
1. ~~API-Endpoint Run-Checks~~ ✅ Erledigt (`POST /api/v1/cases/{id}/run-checks`; Findings werden persistiert).
2. ~~Optional: Ollama-Erreichbarkeit im Health-Check~~ ✅ Erledigt.
3. ~~VVT: Fingerprinting, kanonisches Modell, Mapping, Frontend-Ansicht~~ ✅ Erledigt (`GET /cases/{id}/vvt-normalization`, VVTNormalizationView mit API). Export Ziel-Template optional in Folgesprint.

---

## Phase 3: Cross-Document & Artefakte

**Ziel:** Konsistenzprüfungen über Dokumente hinweg, DSB-Reports, kommentierte Rückgabedokumente.

- **Consistency Engine:** Multi-Dokument-Kontext für LLM; Cross-Document-Findings.
- **Artefakte:** DSB Summary Report (Markdown/PDF); kommentierte DOCX/PDF.
- **Feedback:** Finding-Status (Accepted/Overruled/Fixed) in UI; Audit bei Statusänderungen.

---

## Phase 4: Produktionsreife

**Ziel:** Sicherheit, Skalierung, Nachvollziehbarkeit.

- **Sicherheit:** Authentifizierung (OAuth2/OIDC), RBAC.
- **Betrieb:** Celery (o. ä.) für lange LLM-/Export-Jobs; Logging/Monitoring.
- **Audit:** Unveränderlicher Audit-Log für Aktionen und Check-Läufe.

---

## Legende

| Symbol | Bedeutung |
| :--- | :--- |
| ✅ | Erledigt |
| ⚠️ | Teilweise / Nachbesserung nötig |
| ❌ | Noch nicht umgesetzt |
