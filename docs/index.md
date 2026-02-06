# Datenschutzagent – Dokumentation

Willkommen in der Dokumentation des **Datenschutzagenten**: ein KI-gestützter Assistent für die Vorprüfung von Forschungsvorhaben aus Sicht des Datenschutzes (DSB, Art. 13/14, VVT, DSFA, AVV).

---

## Überblick

*   **Case-Verwaltung:** Vorgänge (Forschungsvorhaben) anlegen, mit Metadaten und Status.
*   **Dokumente:** Upload von DOCX, PDF, XLSX; automatische Textextraktion und Speicherung.
*   **Playbooks:** Versionierte Prüfregeln (JSON); CRUD über die API.
*   **Check Runner:** Einzelchecks gegen Dokumententext per LLM (Ollama/PydanticAI); strukturierte Findings.
*   **Storage:** Lokal oder MinIO (S3-kompatibel).

**Umgesetzt:** Run-Checks pro Case mit persistierten Findings, VVT-Normalisierung, DSB-Reports, kommentierte Rückgabedokumente (DOCX/PDF), Audit-Log und Activity-Timeline, optionale RAG-Variante (Weaviate), OCR für gescannte PDFs, asynchrone Dokument-Extraktion (Celery). **Offen:** AuthN/AuthZ, Retention/Archivierung.

---

## Aktueller Stand

| Bereiche | Status |
| :--- | :--- |
| Cases, Dokumenten-Upload, Textextraktion, Playbook-CRUD, LLM/Check Runner, Storage (lokal + MinIO) | ✅ umgesetzt |
| Run-Checks (Volltext + RAG), VVT, DSB-Report, annotierte Dokumente, Audit, Activity-Timeline, Tests (pytest, Vitest), CI | ✅ umgesetzt |
| AuthN/AuthZ, Retention/Archivierung | ❌ offen |

Details: [Roadmap](roadmap.md), [Gap-Analyse](requirements_gap.md).

---

## Schnellzugriff

*   [Roadmap](roadmap.md) – Phasen und To-dos.
*   [Architektur](architecture.md) – Technik und Komponenten.
*   [Requirements & Gap-Analyse](requirements_gap.md) – Abgleich mit der Projektbeschreibung.
*   [API Reference](api.md) – REST-Endpoints.

---

## Projekt starten

**Voraussetzungen:** Docker, Docker Compose, Ollama (lokal oder im Netz erreichbar).

```bash
docker compose up -d
```

*   Frontend: `http://localhost:3001` (Docker) bzw. `http://localhost:5173` (npm run dev)
*   Backend: `http://localhost:8002` (Docker) bzw. `http://localhost:8000` (uvicorn)
*   API-Doku: `http://localhost:8000/docs` (bzw. Port 8002 bei Docker)

Ollama über `.env` konfigurieren (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`). Aus dem Backend-Container z. B. `http://host.docker.internal:11434` verwenden.
