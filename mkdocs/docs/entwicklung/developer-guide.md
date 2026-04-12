# Developer Guide

Anleitung für Entwickler, um den DatenschutzAgent lokal zu entwickeln, zu testen und zu deployen.

---

## Projektstruktur

```
Datenschutzagent/
├── backend/                    # FastAPI-Backend (Python)
│   ├── app/
│   │   ├── api/routes/        # REST API Endpoints
│   │   ├── core/              # Auth, LLM, Request-Handling
│   │   ├── models/            # Database & Pydantic Models
│   │   ├── services/          # Business Logic (LLM, Storage, etc.)
│   │   ├── data/              # Config Files (org_profiles, playbooks, fachbereiche.yaml)
│   │   └── storage.py         # Storage Backend (Local / MinIO)
│   ├── tests/                 # Unit & Integration Tests (pytest)
│   ├── requirements.txt
│   └── main.py
│
├── src/app/                   # Frontend (React + TypeScript)
│   ├── components/            # React Components (UI, Pages, Modals)
│   ├── lib/                   # Utilities (API Client, Hooks, Helpers)
│   └── styles/                # Tailwind + Custom CSS
│
├── mkdocs/                    # Documentation (MkDocs + Material)
│   ├── docs/
│   ├── mkdocs.yml
│   └── requirements-docs.txt
│
├── docker-compose.yml         # Complete Stack (Frontend, Backend, DB, Cache, Weaviate)
├── .env.example               # Environment Variables Template
└── package.json               # Frontend Dependencies (Node.js)
```

---

## Backend-Entwicklung

### Setup

#### 1. Python-Umgebung
```bash
cd backend
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Datenbank initialisieren
```bash
# Mit PostgreSQL-Container (docker-compose)
docker-compose up -d postgres

# Oder lokal bei PostgreSQL-Installation
export DATABASE_URL=postgresql://user:password@localhost:5432/datenschutzagent
alembic upgrade head
```

#### 3. Environment-Variablen
```bash
cp ../.env.example ../.env
# Edit .env:
# - DATABASE_URL
# - STORAGE_BACKEND
# - OLLAMA_BASE_URL
# - SECRET_KEY (for JWT)
```

#### 4. Server starten
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend läuft unter: http://localhost:8000
- API-Docs (Swagger): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Neue API-Routes erstellen

#### 1. Route-Datei anlegen
Datei: `backend/app/api/routes/my_feature.py`
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db

router = APIRouter(prefix="/my-feature", tags=["My Feature"])

@router.get("", summary="List my features")
async def list_features(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """List all features."""
    return {"features": []}

@router.post("", summary="Create a feature")
async def create_feature(
    request: MyFeatureCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Create a new feature."""
    return {"id": "...", "created": True}
```

#### 2. Route registrieren
Datei: `backend/app/main.py`
```python
from app.api.routes import my_feature

app.include_router(my_feature.router, prefix="/api/v1")
```

#### 3. Models definieren
Datei: `backend/app/models/schemas.py` (Pydantic) & `backend/app/models/db.py` (SQLAlchemy)
```python
# schemas.py (Input/Output)
class MyFeatureCreate(BaseModel):
    name: str
    description: str

# db.py (Database)
class MyFeatureModel(Base):
    __tablename__ = "my_features"
    id = Column(UUID, primary_key=True)
    name = Column(String, nullable=False)
```

### Testing

#### Unit Tests (pytest)
```bash
# Alle Tests
pytest tests/

# Spezifische Test-Datei
pytest tests/test_api.py -v

# Mit Coverage
pytest tests/ --cov=app --cov-report=html
```

#### Test-Template
Datei: `backend/tests/test_my_feature.py`
```python
import pytest
from app.models.schemas import MyFeatureCreate

@pytest.mark.asyncio
async def test_create_feature(client, admin_user):
    response = await client.post(
        "/api/v1/my-feature/",
        json={"name": "Test", "description": "Test feature"},
        headers={"Authorization": f"Bearer {admin_user.token}"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Test"
```

#### Integration Tests
```bash
# Mit Docker-Compose-Stack
docker-compose up -d
pytest tests/ --env docker
```

### Datenbank-Migrationen

#### Neue Migration erstellen
```bash
alembic revision --autogenerate -m "add new table"
```

#### Migration durchführen
```bash
alembic upgrade head
```

#### Migrationen prüfen
```bash
alembic current
alembic history
```

### LLM-Integration (Ollama + PydanticAI)

Beispiel: Check-Ausführung mit LLM

**Datei:** `backend/app/services/check_runner.py`
```python
from pydantic_ai import Agent
from app.core.llm import create_ollama_agent

async def run_check(
    document_text: str,
    check_instruction: str,
    language: str = "de",
) -> CheckResult:
    agent = create_ollama_agent(model="llama2")
    
    prompt = f"""
    Anweisung: {check_instruction}
    
    Dokument:
    {document_text}
    
    Evaluiere das Dokument anhand der Anweisung.
    """
    
    result = await agent.run(prompt)
    return CheckResult(
        compliance=result.compliance,
        severity=result.severity,
        evidence=result.evidence,
    )
```

---

## Frontend-Entwicklung

### Setup

#### 1. Dependencies
```bash
npm install
# oder
pnpm install
```

#### 2. Dev-Server
```bash
npm run dev
```

Frontend läuft unter: http://localhost:5173

#### 3. Environment-Variablen
Datei: `.env` (root)
```
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_NAME=Datenschutzagent
```

### Komponenten-Struktur

```
src/app/components/
├── ui/                        # Basis-Components (Button, Dialog, Table, etc.)
├── case-detail/               # Case-Detail Seite (Tabs)
├── annotated-documents-view.tsx
├── dashboard-stats.tsx
├── document-upload-zone.tsx
├── App.tsx                    # Root Component & Routing
└── ...
```

### Neue Seiten/Features

#### 1. Page-Komponente erstellen
Datei: `src/app/components/my-feature-page.tsx`
```typescript
import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function MyFeaturePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["my-features"],
    queryFn: () => api.get("/my-feature/"),
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">My Features</h1>
      {/* Feature content */}
    </div>
  );
}
```

#### 2. Routing hinzufügen
Datei: `src/app/App.tsx`
```typescript
import { MyFeaturePage } from "./components/my-feature-page";

export function App() {
  return (
    <Router>
      <Routes>
        <Route path="/my-feature" element={<MyFeaturePage />} />
      </Routes>
    </Router>
  );
}
```

### API-Calls

**Datei:** `src/app/lib/api.ts`
```typescript
export const api = {
  get: async (path: string) => {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}${path}`, {
      headers: {
        "Authorization": `Bearer ${getToken()}`,
      },
    });
    return response.json();
  },
  
  post: async (path: string, data: any) => {
    return fetch(`${import.meta.env.VITE_API_BASE_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${getToken()}`,
      },
      body: JSON.stringify(data),
    }).then(r => r.json());
  }
};
```

### Testing (Vitest)

```bash
# Run tests
npm run test

# Watch mode
npm run test:watch
```

**Test-Template:** `src/app/components/my-feature.test.tsx`
```typescript
import { render, screen } from "@testing-library/react";
import { MyFeaturePage } from "./my-feature-page";

describe("MyFeaturePage", () => {
  it("renders title", () => {
    render(<MyFeaturePage />);
    expect(screen.getByText("My Features")).toBeInTheDocument();
  });
});
```

---

## Docker-Entwicklung

### Kompletter Stack
```bash
docker-compose up -d

# Anmeldung
# Frontend: http://localhost:3002
# Backend: http://localhost:8002/docs
# MinIO: http://localhost:9001 (user: minioadmin, password: minioadmin)
```

### Logs verfolgen
```bash
# Backend-Logs
docker-compose logs -f backend

# Alle Logs
docker-compose logs -f
```

### Neustart
```bash
docker-compose restart backend
docker-compose restart frontend
```

### Datenbank zurücksetzen
```bash
docker-compose down -v
docker-compose up -d
```

---

## Git-Workflow

### Branch erstellen
```bash
git checkout -b feature/my-feature
```

### Commits
```bash
git add .
git commit -m "Add feature XYZ"
# Commit-Format: `<type>(<scope>): <message>`
# Types: feat, fix, docs, test, refactor, ci
```

### Tests vor Commit
```bash
# Backend
pytest tests/ -v

# Frontend
npm run test
```

### Pull Request
```bash
git push -u origin feature/my-feature
# Dann auf GitHub PR erstellen
```

---

## Debugging

### Backend-Debugging (VSCode)

**Datei:** `.vscode/launch.json`
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Debugger",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "jinja": true,
      "justMyCode": true
    }
  ]
}
```

### Frontend-Debugging
```bash
# Browser DevTools öffnen (F12)
# React DevTools Extension installieren
```

### Database-Debugging
```bash
# PostgreSQL CLI
psql -h localhost -U postgres -d datenschutzagent

# Alle Cases anzeigen
SELECT id, title, status FROM cases;
```

---

## Performance & Best Practices

### Backend
- **Async/Await:** Verwende `async def` für I/O-Operationen
- **Database:** Nutze `select()` und `where()` für Queries
- **Caching:** Response-Caching für statische Daten (`@cache_dependency`)
- **Logging:** Strukturiertes Logging (JSON) via `python-json-logger`

### Frontend
- **Code Splitting:** Lazy-Loading von Routes (`React.lazy`)
- **Memoization:** `React.memo()` für Performance
- **API Caching:** React Query mit staleTime/gcTime
- **Bundle Size:** Tree-Shaking, externe CDN für große Libraries

---

## Dokumentation aktualisieren

Nach Feature-Implementierung:

1. **API-Dokumentation** (`docs/referenz/api-erweitert.md`)
2. **Benutzerhandbuch** (`docs/benutzerhandbuch/`)
3. **Architektur-Diagramm** (`docs/referenz/architecture.md`)

MkDocs lokal testen:
```bash
cd mkdocs
mkdocs serve

# Oder vom Root
mkdocs serve -f mkdocs/mkdocs.yml
```

---

## Troubleshooting

### Backend starten fehlgeschlagen
```bash
# Check environment variables
env | grep DATABASE_URL

# Check Database-Verbindung
psql $DATABASE_URL

# Migrations durchführen
alembic upgrade head
```

### Frontend zeigt API-Fehler
```bash
# Check Backend läuft
curl http://localhost:8000/health

# Check CORS-Konfiguration in .env
# CORS_ORIGINS=http://localhost:5173
```

### Tests fehlgeschlagen
```bash
# Isolierte Test ausführen
pytest tests/test_api.py::test_specific_test -v

# Mit Debug-Output
pytest tests/ -v -s
```

---

## Ressourcen

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)
- [MkDocs](https://www.mkdocs.org/)
