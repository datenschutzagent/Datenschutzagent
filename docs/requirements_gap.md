# Requirements Gap Analysis

Abgleich der Projektbeschreibung (Anforderungen) mit dem aktuellen Implementierungsstand.

---

## 1. Funktionale Anforderungen

### A) Vorgangsverwaltung (Case Management)

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Vorgang anlegen mit Metadaten | ✅ | Backend + Frontend; API Create/Update. |
| Mehrere Dokumente je Vorgang | ⚠️ | Pro Request ein Upload; Mehrfach-Upload in einem Request nicht implementiert. |
| Versionierung (Stände je Dokument) | ❌ | Keine Logik für v1/v2 pro Dokumenttyp. |
| Statusmodell | ✅ | `CaseStatusEnum`; Status im Case-Modell. |
| Vorgang löschen | ✅ | `DELETE /api/v1/cases/{id}`. |

### B) Dokumentverarbeitung

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Formate DOCX, PDF, XLSX | ✅ | `document_processor.py` (PyMuPDF, python-docx, openpyxl). |
| Text- und Strukturextraktion | ✅ | Bei Upload; Speicherung in `Document.content`. |
| OCR (gescannte PDFs) | ❌ | Kein Tesseract/OCR. |
| DE/EN | ⚠️ | Case hat `language`; Playbook/Checks sprachabhängig noch nicht ausgebaut. |

### C) Playbook-basierte Vorprüfung

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Playbooks im System, versioniert | ✅ | `Playbook`-Modell (JSONB), CRUD unter `/api/v1/playbooks/`. |
| Dokument-Checks | ✅ | `check_runner.run_check()` mit PydanticAI/Ollama; strukturiertes Ergebnis. |
| Vorgangs-/Cross-Document-Checks | ❌ | Kein Multi-Dokument-Kontext; keine Cross-Doc-Findings. |
| Check-Lauf pro Case + persistente Findings | ✅ | `POST /api/v1/cases/{id}/run-checks`; Check Runner wird aufgerufen, Findings in DB gespeichert. |

### D) VVT-Normalisierung

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Template-Fingerprinting | ✅ | Im VVT-Service (LLM); `source_template` in `GET /cases/{id}/vvt-normalization`. |
| Kanonisches VVT-Datenmodell | ✅ | Pydantic-Schema (`VVTFieldResponse`, `VVTNormalizationResponse`); LLM-Mapping in `vvt_service.py`. |
| Export Ziel-Template | ❌ | Noch nicht implementiert (optional Folgesprint). |

### E) Artefakte / Output

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| DSB Summary Report | ❌ | Keine Report-Generierung. |
| Kommentierte Dokumente (DOCX/PDF) | ❌ | Keine Kommentar-/Annotation-Erzeugung. |
| Findings maschinenlesbar (JSON) | ✅ | Finding-Modell, Case-Response inkl. Findings, Erzeugung via Run-Checks; PATCH `/api/v1/findings/{id}` für Status. |

### F) Auditierbarkeit

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| Logging Playbook-/Modell-Version, Check-Läufe | ❌ | Kein strukturierter Audit-Log. |
| Finding-Status accepted/overruled/fixed | ✅ | Enum und DB-Felder; `PATCH /api/v1/findings/{id}`; UI in Case-Detail (Status-Buttons) implementiert. |

---

## 2. Nicht-funktionale Anforderungen

| Anforderung | Status | Anmerkung |
| :--- | :--- | :--- |
| On-Prem / datenschutzkonform (LLM lokal) | ✅ | Ollama; Konfiguration über `OLLAMA_*`. |
| Storage (lokal + MinIO) | ✅ | `storage.py`: Backends umschaltbar. |
| AuthN/AuthZ, Rollen | ❌ | Nicht implementiert. |
| Retention/Archivierung konfigurierbar | ❌ | Nicht implementiert. |
| Reproduzierbarkeit (Playbook-/Modellversion) | ⚠️ | Playbook versioniert; Verknüpfung Check-Lauf ↔ Version noch nicht geloggt. |

---

## 3. Priorisierte Schritte (Gap-Schließung)

1. ~~**Run-Checks-API**~~ ✅ Erledigt. ~~**Frontend**~~ ✅ Erledigt (Cases, Documents, Findings, Playbooks, Run-Checks, Finding-Status nutzen echte API).
2. ~~**VVT:** Fingerprinting, kanonisches Modell, Mapping, Frontend-Ansicht~~ ✅ Erledigt (`GET /cases/{id}/vvt-normalization`, `vvt_service.py`, VVTNormalizationView an API). **Export Ziel-Template** noch offen (optional).
3. **Artefakte:** DSB-Report, kommentierte DOCX/PDF.
4. **Sicherheit & Audit:** AuthN/AuthZ, Audit-Log.
