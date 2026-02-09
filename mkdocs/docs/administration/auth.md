# Authentifizierung (OIDC)

Die Anwendung unterstützt optionale **OAuth2/OIDC-Authentifizierung**. Ist OIDC aktiviert (`OIDC_ENABLED=true`), sind alle API-Routen unter `/api/v1` – außer `GET /api/v1/auth/config` – geschützt. Requests ohne gültigen Bearer-Token erhalten **401 Unauthorized**.

## Ablauf

1. **Frontend** lädt beim Start `GET /api/v1/auth/config` (ohne Auth). Die Antwort enthält u. a. `oidc_enabled`, `authorization_endpoint`, `token_endpoint`, `end_session_endpoint`, `oidc_client_id`, `oidc_scopes`.
2. **Nicht eingeloggt:** Das Frontend leitet zur konfigurierten IdP-URL (z. B. Keycloak) weiter. Der Login erfolgt mit **PKCE** (code_challenge / code_verifier).
3. **Callback:** Nach dem Login tauscht das Frontend den Autorisierungscode gegen ein Token aus (gegen token_endpoint). Das Token wird in sessionStorage gehalten und bei API-Aufrufen als `Authorization: Bearer <token>` mitgesendet.
4. **Backend** validiert das JWT (z. B. per JWKS vom OIDC Issuer), liest `sub` und legt bei erstem Login einen User in der Tabelle `users` an (`oidc_sub`). GET `/api/v1/me` liefert den aktuellen User.
5. **Logout:** Token wird gelöscht; optional Redirect zu `end_session_endpoint` des IdP.

## Konfiguration

Siehe [Konfiguration – OAuth2/OIDC](../konfiguration.md). Wichtige Variablen: `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_SCOPES`; optional `OIDC_CLIENT_SECRET`, `OIDC_AUDIENCE`.

## Ohne OIDC

Ist OIDC deaktiviert, wird ein **Default-User** verwendet. Optional kann `CURRENT_USER_ID` (UUID) gesetzt werden, um einen bestimmten User aus der Datenbank zu nutzen. Dann sind die API-Routen ohne Token erreichbar (für Entwicklung/Betrieb ohne IdP).
