# Entwicklung

Dokumentation für Entwickler, die am DatenschutzAgent arbeiten möchten.

---

## Inhalte

### [Developer Guide](developer-guide.md)
Vollständige Anleitung für die lokale Entwicklung:

- **Projektstruktur** – Verzeichnis-Übersicht
- **Backend-Setup** – Python, Datenbank, Ollama
- **Frontend-Setup** – Node.js, Dependencies
- **API-Entwicklung** – Neue Routes, Models, Tests
- **Testing** – Unit-Tests (pytest, Vitest)
- **Docker-Workflow** – Lokale Entwicklung im Container
- **Git-Workflow** – Branching, Commits, PRs
- **Debugging** – Tools und Best Practices
- **Performance** – Optimierungen für Backend & Frontend

---

## Quick Start

```bash
# Backend-Setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend-Setup (in neuem Terminal)
npm install
npm run dev

# Tests
pytest tests/
npm run test
```

---

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL + Ollama
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Database:** PostgreSQL (async via asyncpg)
- **LLM:** Ollama (local inference) + PydanticAI
- **Task Queue:** Celery + Redis (optional)
- **Vector DB:** Weaviate (optional, for RAG)
- **Storage:** Local FS oder MinIO (S3-compatible)

---

## Dokumentation aktualisieren

Nach Änderungen die Dokumentation uptodate halten:

```bash
cd mkdocs
mkdocs serve  # Preview lokal unter http://localhost:8000

# oder vom Root
mkdocs serve -f mkdocs/mkdocs.yml
```

---

## Beitragen

1. **Fork** oder **Branch** erstellen
2. **Feature** implementieren + Tests
3. **Dokumentation** aktualisieren
4. **PR** erstellen mit aussagekräftiger Beschreibung

---

## Ressourcen

- [FastAPI Dokumentation](https://fastapi.tiangolo.com/)
- [React Dokumentation](https://react.dev/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [MkDocs](https://www.mkdocs.org/)
- [Ollama](https://ollama.ai/)
