# Rollen (RBAC)

Jeder Nutzer hat eine **Rolle**, die festlegt, was er in der Anwendung tun darf. Die Rolle wird in `GET /api/v1/me` zurückgegeben; das Frontend blendet Schreib- und Admin-Aktionen für Nutzer mit Rolle **viewer** aus.

## Rollen

| Rolle | Rechte |
| :--- | :--- |
| **viewer** | Nur Lesen: Cases, Dokumente, Playbooks, Findings, VVT, DSB-Report, Annotierte Dokumente, Aktivitäten, Profil (eigenes). Kein Anlegen/Bearbeiten/Löschen, kein Run-Checks, kein Finding-Status ändern, kein Zugriff auf Verwaltung. |
| **editor** | Wie viewer, zusätzlich: Cases/Dokumente/Playbooks anlegen, bearbeiten, löschen; Playbook-Checks ausführen; Finding-Status ändern; Dokument-Kommentare. Kein Zugriff auf Admin-Endpoints (Verwaltung). |
| **admin** | Wie editor, zusätzlich: Zugriff auf Verwaltung (Einstellungen, Verbindungstests). |

## Zuweisung

- **Neue Nutzer (OIDC):** Beim ersten Login wird die Default-Rolle aus **`RBAC_DEFAULT_ROLE`** vergeben (z. B. `viewer`). So können Sie neue Nutzer zunächst nur lesend anlegen.
- **Bestehende Nutzer:** Über die Migration `005_add_user_role.sql` wurden bestehende User auf `editor` gesetzt. Änderungen an Rollen erfolgen über die **CLI** (siehe [CLI](cli.md)): `users set-role <user-uuid> editor` bzw. `admin` oder `viewer`.

## API

- Schreib-Operationen (POST/PATCH/DELETE bei Cases, Documents, Findings, Playbooks; POST Run-Checks) erfordern Rolle **editor** oder **admin**; sonst **403 Insufficient permissions**.
- Admin-Endpoints (`GET /api/v1/admin/settings`, `GET /api/v1/admin/connections`) erfordern Rolle **admin**; sonst 403.
