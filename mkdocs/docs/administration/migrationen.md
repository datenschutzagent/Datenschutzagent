# Datenbank-Migrationen

Schema-Änderungen werden über **[Alembic](https://alembic.sqlalchemy.org/)**
verwaltet — das ist die **einzige Quelle der Wahrheit** für das Datenbankschema.
Die Migrationen liegen unter **`backend/alembic/versions/`**.

Beim Start des Backend-Containers werden ausstehende Migrationen **automatisch**
angewendet (`alembic upgrade head` im Entrypoint, siehe `backend/entrypoint.sh`).

## Vorgehen

**Migrationen anwenden** (bei bestehender Datenbank, z. B. nach einem Update):

```bash
# Im Container
docker compose exec backend alembic upgrade head

# Oder lokal (im Verzeichnis backend/, mit gesetzter DATABASE_URL)
cd backend && alembic upgrade head
```

**Neue Migration erstellen:**

```bash
cd backend
alembic revision -m "beschreibung_der_aenderung"
# Die generierte Datei unter alembic/versions/ ausfüllen (upgrade/downgrade),
# dann anwenden:
alembic upgrade head
```

**Status / Historie:**

```bash
alembic current      # aktuell angewendete Revision
alembic history      # alle Revisionen
alembic downgrade -1 # eine Revision zurück (Vorsicht in Produktion)
```

## Baseline und Alt-Skripte

Die erste Alembic-Migration (`…_baseline.py`) bildet den Schemastand zum
Einführungszeitpunkt von Alembic ab. Sie konsolidiert die früheren, manuell
angewendeten **rohen SQL-Skripte**.

Diese historischen SQL-Skripte (`001_…` bis `021_…`) liegen jetzt unter
**`backend/migrations/legacy/`** und sind **inaktiv** — sie werden nicht mehr
ausgeführt und dienen nur der Nachvollziehbarkeit. Bitte keine neuen rohen
SQL-Dateien anlegen; verwenden Sie stattdessen `alembic revision`.
