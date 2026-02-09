# Datenbank-Migrationen

Die Tabellen der Anwendung werden beim Backend-Start per **`Base.metadata.create_all`** angelegt. Zusätzliche **Schema-Änderungen** (neue Spalten, Tabellen) liegen als SQL-Skripte unter **`backend/migrations/`**. Diese Skripte werden **nicht** automatisch ausgeführt; sie müssen bei bestehenden Datenbanken **einmalig manuell** angewendet werden.

## Vorgehen

Bei einer bestehenden Datenbank (z. B. nach einem Update) die Migrations-Skripte in Reihenfolge ausführen. Beispiele:

**Einzelne Migration (z. B. extraction_method):**
```bash
docker compose exec -T postgres psql -U postgres -d datenschutzagent < backend/migrations/001_add_document_extraction_method.sql
```

**Alle Migrationen nacheinander:**
```bash
for f in backend/migrations/*.sql; do docker compose exec -T postgres psql -U postgres -d datenschutzagent < "$f"; done
```

Lokal (ohne Docker) mit eigenem `psql` und passender `DATABASE_URL` die Skripte gegen die gleiche Datenbank ausführen.

## Wichtige Migrations (Auswahl)

- `001_add_document_extraction_method.sql` – Document um Feld extraction_method (text/ocr) für OCR-Kennzeichnung.
- `002_add_finding_source_strategy.sql` – Finding um source_strategy (full_text/rag).
- `003_add_users.sql` – User-Tabelle.
- `004_add_oidc_sub.sql` – OIDC-Subjekt (oidc_sub) für User.
- `005_add_user_role.sql` – Rolle (viewer/editor/admin) für RBAC.
- `006_add_document_comments.sql` – Dokument-Kommentare.
- `007_prompt_templates.sql` – Prompt-Templates (falls verwendet).

Vor dem Ausführen einer Migration ggf. prüfen, ob die Änderung für Ihre DB-Version bereits angewendet wurde (z. B. Spalte/ Tabelle existiert bereits), um Doppelausführungen zu vermeiden.
