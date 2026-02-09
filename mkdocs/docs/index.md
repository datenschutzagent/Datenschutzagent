# Datenschutzagent – Dokumentation

Willkommen in der Dokumentation des **Datenschutzagenten**: ein KI-gestützter Assistent für die Vorprüfung von Forschungsvorhaben aus Sicht des Datenschutzes (DSB, Art. 13/14, VVT, DSFA, AVV).

---

## Überblick

*   **Case-Verwaltung:** Vorgänge (Forschungsvorhaben) anlegen, mit Metadaten und Status.
*   **Dokumente:** Upload von DOCX, PDF, XLSX; automatische Textextraktion und Speicherung.
*   **Playbooks:** Versionierte Prüfregeln (JSON); CRUD über die API.
*   **Check Runner:** Einzelchecks gegen Dokumententext per LLM (Ollama/PydanticAI); strukturierte Findings.
*   **Storage:** Lokal oder MinIO (S3-kompatibel).

**Umgesetzt:** Run-Checks pro Case mit persistierten Findings, VVT-Normalisierung, DSB-Reports, kommentierte Rückgabedokumente (DOCX/PDF), Audit-Log und Activity-Timeline, optionale RAG-Variante (Weaviate), OCR für gescannte PDFs, asynchrone Dokument-Extraktion (Celery), OAuth2/OIDC und RBAC. **Offen:** Retention/Archivierung.

---

## Aktueller Stand

| Bereiche | Status |
| :--- | :--- |
| Cases, Dokumenten-Upload, Textextraktion, Playbook-CRUD, LLM/Check Runner, Storage (lokal + MinIO) | ✅ umgesetzt |
| Run-Checks (Volltext + RAG), VVT, DSB-Report, annotierte Dokumente, Audit, Activity-Timeline, Tests (pytest, Vitest), CI | ✅ umgesetzt |
| AuthN (OIDC), AuthZ (RBAC), DE/EN, OCR, Weaviate/RAG | ✅ umgesetzt |
| Retention/Archivierung | ❌ offen |

Details: [Roadmap](projekt/roadmap.md), [Gap-Analyse](projekt/requirements_gap.md).

---

## Schnellzugriff

*   [Schnellstart](schnellstart.md) – Projekt starten (Docker, lokal).
*   [Roadmap](projekt/roadmap.md) – Phasen und To-dos.
*   [Architektur](referenz/architecture.md) – Technik und Komponenten.
*   [Requirements & Gap-Analyse](projekt/requirements_gap.md) – Abgleich mit der Projektbeschreibung.
*   [API Reference](referenz/api.md) – REST-Endpoints.
