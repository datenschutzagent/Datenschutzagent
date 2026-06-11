# Legacy SQL-Migrationen (inaktiv)

Diese rohen SQL-Dateien (`001_…` bis `021_…`) stammen aus der Zeit **vor** der
Einführung von Alembic. Sie wurden früher manuell angewendet und sind in den
**Alembic-Baseline** (`backend/alembic/versions/…_baseline.py`) konsolidiert.

**Sie werden nicht mehr ausgeführt** und dienen nur noch der Nachvollziehbarkeit
der Schema-Historie.

## Aktueller Stand: Alembic ist die einzige Quelle der Wahrheit

- Schema-Änderungen erfolgen ausschließlich über Alembic
  (`backend/alembic/versions/`).
- Der Container-Entrypoint führt beim Start `alembic upgrade head` aus
  (siehe `backend/entrypoint.sh`).
- Neue Migrationen:

  ```bash
  cd backend
  alembic revision -m "beschreibung"
  alembic upgrade head
  ```

Bitte **keine** neuen rohen SQL-Dateien hier anlegen.
