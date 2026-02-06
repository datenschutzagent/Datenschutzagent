
  # DatenschutzAgent

  This is a code bundle for DatenschutzAgent. The original project is available at https://www.figma.com/design/cNgohBB9L3a2qlSZskVZuh/DatenschutzAgent.

  ## Running the code

  ### Mit Docker Compose (Frontend + Backend als Container)
  - `.env` anlegen (siehe `.env.example`). **Ollama** wird extern betrieben (z. B. im lokalen Netz) und über `OLLAMA_BASE_URL`, `OLLAMA_MODEL` etc. in `.env` konfiguriert.
  - `docker compose up -d` startet Postgres, MinIO, Redis, Backend und Frontend.
  - Frontend: http://localhost:3000
  - Backend/API-Docs: http://localhost:8000/docs

  ### Lokale Entwicklung
  - **Frontend**: `npm i` und `npm run dev`.
  - **Backend**: `docker compose up -d postgres redis` (nur Infrastruktur), dann im Backend-Verzeichnis `pip install -r requirements.txt` und `uvicorn app.main:app --reload --port 8000`.
  - Ollama lokal oder im Netz: in `.env` z. B. `OLLAMA_BASE_URL=http://localhost:11434`, `OLLAMA_MODEL=llama3.2`.

  ### API overview
  - **Cases**: `GET/POST /api/v1/cases`, `GET/PATCH/DELETE /api/v1/cases/{id}`.
  - **Documents**: `GET /api/v1/documents?case_id=...`, `POST /api/v1/documents` (form: `case_id`, `file`, `document_type`, `uploaded_by`), `GET /api/v1/documents/{id}`.
  