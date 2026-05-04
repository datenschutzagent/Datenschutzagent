# Sicherheits-Audit – OWASP Top 10 (Datenschutzagent)

Stand: 2026-05-04
Branch: `claude/security-audit-owasp-oR4jb`
Scope: Backend (FastAPI/Python 3.11), Frontend (React/Vite/TypeScript), Konfiguration (Docker, nginx, CI).

## Vorgehen

- Toolgestützt
  - **Bandit 1.9.4** auf `backend/app/`
  - **pip-audit 2.10.0** auf `backend/requirements.txt`
  - **npm audit** auf `package.json`
  - GitHub Workflow (`.github/workflows/...`) prüft zusätzlich Semgrep `p/owasp-top-ten` + `p/secrets`
- Manuell
  - Routen-Mapping (`backend/app/api/__init__.py`), AuthZ-Coverage (`require_roles`), Object-Level-Authorization
  - Auth-Pfad (OIDC, Session-Cookies, CSRF), Crypto (Fernet), Storage (Path-Traversal), SSRF (Webhooks)
  - LLM-Pfade (Prompt-Injection, Token-DoS), Input-Validierung (Pydantic-Limits), Logging/Observability
  - CSP/HSTS/Cookies-Headers, CORS, Rate-Limiter, Container/Runtime

## Toolergebnisse – Zusammenfassung

| Tool       | Befunde                                         | Anmerkung |
|------------|-------------------------------------------------|-----------|
| Bandit     | 13 × MEDIUM (alle B608), 9 × LOW (B105/B110/B311) | Alle B608 nach Review **false positives** (siehe unten). |
| pip-audit  | **0** bekannte CVE in `requirements.txt`         | Sehr gut; sollte im wöchentlichen CI bleiben. |
| npm audit  | **1 × moderate**: `postcss <8.4.31` (XSS in Stringify) | Build-Tool, indirect via `@tailwindcss/vite`/`vite`. Update empfohlen. |

Die Bandit-B608-Treffer in `backend/app/services/analytics_service.py`, `backend/app/services/retention_service.py` und `backend/app/api/routes/analytics.py` sind **keine SQL-Injection**: Die per f-String eingebauten Fragmente (`dept_filter`, `_retention_base_sql()`, …) sind hartcodierte Konstanten; die tatsächlichen Nutzereingaben (z. B. `:dept`) werden ausschließlich über benannte Bind-Parameter eingebunden. Empfehlung: `# nosec B608 -- only static fragments interpolated; user input via :params` an den Stellen ergänzen, damit das CI-Rauschen verschwindet.

---

## Bewertete Stärken (Bestand)

Das Projekt hat bereits viele Härtungen umgesetzt; die folgenden Punkte sind als positiv festgehalten und sollten nicht "rückwärts" gefixt werden:

- **Produktions-Validator** (`config.py::_validate_production_profile`): erzwingt OIDC, kein DEBUG, gesetzten Webhook-Schlüssel, HTTPS-only CORS.
- **CORS-Validator**: lehnt Wildcards/Regex-Zeichen ab, prüft Schema/Hostname.
- **Security-Header** (`main.py::add_security_headers`): X-Content-Type-Options, X-Frame-Options=DENY, Permissions-Policy, Referrer-Policy, CSP, HSTS (nur unter HTTPS+!debug).
- **SSRF-Schutz für Webhooks**: Validierung beim Anlegen + **DNS-Rebinding-Re-Check vor jedem Delivery** (`webhook_service.py::_assert_no_ssrf`).
- **Path-Traversal-Schutz** im Local-Storage (`storage.py::_LocalBackend._resolve` mit `is_relative_to`).
- **Magic-Byte-Validierung** beim Upload (`documents.py::_verify_magic_bytes`), explizite Allow-List statt MIME.
- **Prompt-Injection-Erkennung** (`core/prompt_security.py`) inkl. Block-Modus + Format-String-Escaping.
- **HMAC-signierte Webhooks**, **Fernet-verschlüsselte Webhook-Secrets** in DB (Pflicht in Produktion).
- **Rate-Limiter mit Trusted-Proxy-Whitelist** (kein blindes Vertrauen auf `X-Forwarded-For`).
- **Session-Cookie-Flow**: `HttpOnly`+`Secure`+`SameSite=strict`+`__Host-` Prefix in Produktion, Double-Submit-CSRF.
- **OIDC-JWT**: JWKS-Cache mit Lock, Issuer- und Audience-Verifikation (Audience Pflicht).
- **RBAC** über `require_roles`-Dependency.
- **Container**: Non-root-User, Build-Tools nach Install entfernt; Compose ohne Postgres/Redis/MinIO-Port-Mapping.
- **Docs disabled in production** (`docs_url`/`openapi.json` nur bei DEBUG).
- **Pre-commit-Hooks**: `detect-secrets`, `bandit`, plus wöchentlicher CI-Lauf (Bandit, pip-audit, npm-audit, Semgrep).

---

## Befunde, gemappt auf OWASP Top 10 (2021)

Priorisierung: **P0** = sofort, **P1** = nächster Sprint, **P2** = mittelfristig, **P3** = Hygiene.

### P0 – sofort beheben

#### 1. **A07 – Identification & Authentication Failures**: fehlendes `await` auf JWT-Verifikation im Session-Cookie-Pfad
- **Datei**: `backend/app/api/routes/auth.py:157`
- **Beobachtung**: `claims = _verify_jwt(id_token)` ruft eine `async`-Funktion synchron auf → `claims` ist eine **Coroutine**, kein Dict. `claims.get("sub")` wirft `AttributeError`. Der Session-Cookie-Flow ist damit komplett funktionslos (`AUTH_SESSION_COOKIE_ENABLED=true` führt zu 500).
- **Risiko**: Aktuell **kein Bypass** (failure-closed), aber:
  1. Indikator dafür, dass der Pfad ungetestet ist;
  2. ein "schneller Fix" ohne Re-Validation könnte die JWT-Prüfung umgehen.
- **Maßnahme**:
  - `claims = await _verify_jwt(id_token)` und Endpunkt-Funktion bleibt `async` (ist sie bereits).
  - Pytest-Integrationstest für den `POST /auth/session`-Pfad mit gemocktem IdP/JWKS hinzufügen.

#### 2. **A03 – Injection (LLM Prompt Injection)**: User-Eingabe & Chat-Historie ungeprüft im Chat-Prompt
- **Datei**: `backend/app/services/finding_chat_service.py:80–88` und `findings.py:610`
- **Beobachtung**: Felder des Findings werden via `sanitize_prompt_field` gereinigt, **aber** `user_message` und die persistente Chat-Historie werden **direkt** in den User-Content konkateniert (`f"Nutzer: {user_message}"`). `FindingChatMessageCreate.content` hat **keinen `max_length`**.
- **Risiko**: Klassischer Prompt-Injection-Vektor (OWASP LLM01). Da das LLM später z. T. operationale Outputs (DSB-Berichte, Findings) erzeugt, kann ein Angreifer mit Editor-Rolle die Tonalität / Empfehlungen manipulieren oder über Folgekonversationen Daten anderer Befunde unterminieren. Kombiniert mit **fehlendem `max_length`** außerdem Token-/Speicher-DoS.
- **Maßnahme**:
  - `sanitize_prompt_field(user_message, max_chars=2000)` vor Einbettung in den Prompt.
  - Chat-History ebenfalls pro Nachricht reinigen + Gesamt-Char-Budget (z. B. 8 000) cappen.
  - In `_schemas/finding.py:115` `FindingChatMessageCreate.content` auf `Field(..., min_length=1, max_length=4000)` beschränken.
  - Logging des `prompt_injection_attempt`-Events bleibt, aber `prompt_injection_block` greift dann auch hier.

#### 3. **A01 – Broken Access Control**: keine objekt-/abteilungsbezogene Autorisierung
- **Dateien**: `cases.py`, `documents.py`, `findings.py`, `vvt_overview.py`, `dsr.py`, `data_breaches.py` etc.
- **Beobachtung**: `require_roles("viewer", …)` prüft nur die globale Rolle. Es gibt **keine Bindung User ↔ Case/Department**. Jeder authentifizierte Viewer kann
  - jeden Case lesen (`GET /cases/{id}`),
  - jedes Dokument herunterladen (`GET /documents/{id}/download`),
  - die org-weite VVT-Liste samt CSV (`GET /vvt-overview/export`, bis 5 000 Zeilen) ziehen,
  - jede DSR-Anfrage / Datenpanne lesen.
- **Risiko**: In einem **DSGVO-Compliance-Tool** sind Cases häufig selbst personenbezogen (DSAR-Antragsteller, Datenpannen-Betroffene, Mitarbeiterfälle). Eine globale Sichtbarkeit auch nur für Viewer-Rollen ist mit den GDPR-Grundsätzen "Need to know" / Art. 5 Abs. 1 lit. f schwer vereinbar.
- **Maßnahme** (gestaffelt):
  - **Kurzfristig**: explizite Entscheidung dokumentieren (z. B. Hinweis im Admin-Handbuch: "Viewer = Datenschutzbeauftragter mit Vollsicht"). Sicherstellen, dass Viewer im Onboarding nur DSBs sind.
  - **Mittelfristig**: Department-Scoping pro User (`UserModel.allowed_departments: list[str]`) + zentralen `ensure_can_access_case(user, case)`-Helper, der in jeder Case-/Document-/Finding-/DSR-Route aufgerufen wird. Audit-Log-Eintrag `permission_denied` bei Verstoß.
  - Inkonsistenz beheben: `vvt_overview.py` hat **keinerlei** `require_roles`-Guard (nur globale Auth) – mindestens `require_roles("viewer", "editor", "admin")` ergänzen, um zur Restbasis konsistent zu sein.

---

### P1 – nächster Sprint

#### 4. **A04 – Insecure Design**: keine Längen-/Größenlimits auf Pflege-Endpunkten
- `backend/app/models/_schemas/admin.py::UserUpdate`
  - `display_name: str | None = None` ohne `max_length` → DB-Column ist `String(200)`, würde DB-seitig fehlschlagen, aber der 422-Check fehlt.
  - `email: str | None = None` ohne `max_length` und ohne `EmailStr`/Format-Check.
  - `preferences: dict[str, Any] | None = None` (Free-Form-JSONB) ohne Größenlimit – **Storage-DoS** möglich (PATCH /me beliebig groß).
- `backend/app/models/_schemas/finding.py:115` `FindingChatMessageCreate.content` ohne `max_length` (siehe Befund 2).
- **Maßnahme**: konsistente `Field(..., max_length=…)`-Limits, `EmailStr` für Mail-Felder, `preferences` strikt typisieren (`UserPreferences`-Modell ist schon da, sollte das einzige Eingabe-Schema sein) und Total-Bytes-Cap (~4 KB) per Validator.

#### 5. **A05 – Security Misconfiguration**: CSP erlaubt `style-src 'unsafe-inline'`
- `backend/app/main.py::add_security_headers` und `nginx.conf`
- `dangerouslySetInnerHTML` in `src/app/components/ui/chart.tsx:83-99` nutzt das aus.
- **Risiko**: Schwächt CSP gegen reflektives XSS. Auch wenn das Projekt aktuell keinen direkten User-XSS-Vektor zeigt, eliminiert ein striktes CSP einen Großteil der "wenn doch mal" Klasse.
- **Maßnahme**:
  - Variante A: per Build-Step Nonce in `<style>` injizieren und `style-src 'self' 'nonce-…'` setzen.
  - Variante B: `chart.tsx` auf CSS-Variablen am `:root`-Element umstellen statt `<style dangerouslySetInnerHTML>` und `'unsafe-inline'` aus `style-src` entfernen.

#### 6. **A09 – Security Logging & Monitoring Failures**: LLM-Fehler-Detail leakt an Client
- `backend/app/api/routes/findings.py:628`: `raise HTTPException(status_code=502, detail=f"LLM-Fehler: {exc}")` reicht den Original-Provider-Fehler (inkl. URLs/Stack-Auszüge) an den Browser durch.
- Ähnliche Muster in DSFA-/DSB-Generierung prüfen.
- **Maßnahme**: Client erhält generische Meldung (`"LLM-Anfrage fehlgeschlagen"`), Detail nur ins Log + `request_id` zur Korrelation; bei Bedarf `error_code` per RFC 7807 mitgeben.

#### 7. **A05 – Security Misconfiguration**: `metrics_allowed_ips` unterstützt nur exakte IPs
- `backend/app/main.py::prometheus_metrics`: vergleicht `client_ip not in allowed_ips` als String-Liste. Anders als `trusted_proxies` (CIDR-fähig) funktioniert hier ein Eintrag wie `10.0.0.0/8` nicht.
- **Maßnahme**: gleichen Helper wie für `trusted_proxies` nutzen (`ipaddress.ip_network(..., strict=False)` + `peer_addr in net`).

#### 8. **A07 – Authentication Failures (defense-in-depth)**: Logout ohne CSRF-Validierung
- `auth.py::logout` löscht die Session ohne `verify_csrf`. Logout-CSRF gilt als minder-kritisch, ist aber bei `__Host-`-Cookies + SameSite=strict realistisch durch Subdomain-Takeover/CORS-Misconfig wieder erreichbar.
- **Maßnahme**: `verify_csrf(request, payload['csrf'])` analog zu `get_current_user_cookie` ausführen.

---

### P2 – mittelfristig

#### 9. **A06 – Vulnerable Components**: `postcss < 8.4.31` (moderate XSS via Stringify)
- `npm audit` flaggt eine moderate CVE über transitive `postcss`. Build-Time-Tool, **nicht** im Runtime-Bundle, aber Hygiene-relevant.
- **Maßnahme**: `npm update postcss` (ggf. `overrides` in `package.json`), CI weiter `--audit-level=high` lassen, separat `npm audit` informativ in PR-Reports rendern.

#### 10. **A03 – Injection (Bandit-Rauschen)**: SQL-Fragments per f-String trotz Bind-Parameter
- 13 × B608, alle false positives (siehe oben), aber das CI-Rauschen erschwert das Erkennen echter Treffer.
- **Maßnahme**: pro Stelle `# nosec B608 -- static fragment, params bound via :name` anbringen oder die Fragmente als `Literal[…]` parametrisieren, sodass Bandit sie nicht mehr als f-String erkennt.

#### 11. **A02 – Cryptographic Failures (low risk)**: `random.uniform` für Webhook-Backoff-Jitter
- `backend/app/services/webhook_service.py:60` (B311). Jitter ist nicht sicherheitskritisch, aber `secrets.SystemRandom().uniform(...)` kostet nichts und macht den Bandit-Eintrag obsolet.

#### 12. **A04 – Insecure Design**: `default_user`-Fallback in Produktion zu locker (defense-in-depth)
- Wenn `OIDC_ENABLED=false` (durch Production-Validator unterbunden), aber falls der Validator je gelockert würde, antwortet die API allen Anfragenden als Default-User (Rolle `viewer`, aber inkl. Lese-Vollsicht – siehe Befund 3).
- **Maßnahme**: Im `lifespan` zusätzlich `assert settings.app_environment != "production" or settings.oidc_enabled` (Belt-and-Suspenders), und in `get_current_user_fallback` einen expliziten Log-Warnruf pro Aufruf in non-development.

#### 13. **A05 – Security Misconfiguration**: `Strict-Transport-Security` ohne `preload`
- Kein Blocker; wenn die App in der HSTS-Preload-Liste landen soll, ist `; preload` + `; includeSubDomains` Pflicht und ein bewusster Schritt.

---

### P3 – Hygiene / Best Practice

#### 14. **A09 – Logging**: PII in Audit-/Access-Logs
- `app.access` loggt Pfade ohne Path-Param-Maskierung; Path-Param ist UUID, kein PII. OK.
- `prompt_injection_attempt`-Event loggt 100 Zeichen `value_preview` – bei Datenpannen-Schilderungen ggf. PII. Erwägen: Hash + Länge statt Klartext.

#### 15. **A05 – Misconfig**: `redoc_url`/`docs_url`/`openapi_url` an `DEBUG` gekoppelt
- Reicht aktuell, weil `_validate_production_profile` `DEBUG=false` erzwingt. Robuster: zusätzlich `app_environment != "production"` prüfen, damit Versehen außerhalb von Compose nicht durchschlagen.

#### 16. **A05 – Misconfig**: OIDC-Discovery wird pro `GET /auth/config` live geholt
- `routes/auth.py:46-51` macht synchronen `urlopen` mit 3 s Timeout pro Request. Per-IP-Rate-Limit existiert (`30/minute`), trotzdem unnötig teuer und ein Single-Point-of-Failure.
- **Maßnahme**: 5-min Process-lokaler Cache (analog `_jwks_cache`).

#### 17. **A04 – Robustness**: Default-User-Erstellung in `lifespan` ist racy
- Bei mehreren Workern können zwei gleichzeitig den Insert versuchen. Aktuell durch `oidc_sub`-Unique-Constraint gemildert; Default-User ohne `oidc_sub` würde knallen, wenn die ID schon existiert (`scalar_one_or_none() is None` reicht). Vermutlich harmlos.
- **Maßnahme**: `INSERT ... ON CONFLICT DO NOTHING` (PostgreSQL) statt Read-then-Write.

---

## Priorisierter Aktionsplan

| # | Befund                                                   | OWASP | Aufwand | Risiko | Priorität |
|---|----------------------------------------------------------|-------|---------|--------|-----------|
| 1 | `await _verify_jwt` + Tests im Session-Flow              | A07   | XS      | Hoch (latent) | **P0** |
| 2 | Prompt-Injection-Sanitizer für `user_message` + History; `max_length` auf Chat-Content | A03 / LLM01 | S | Hoch | **P0** |
| 3 | Object-Level-AuthZ-Helper + Department-Scoping; `vvt_overview` `require_roles` ergänzen | A01 | M–L | Hoch | **P0**(Konsistenz) / **P1**(Scoping) |
| 4 | Längen-/Größenlimits in `UserUpdate`, `FindingChatMessageCreate`; `EmailStr` | A04 | S | Mittel | P1 |
| 5 | CSP ohne `style-src 'unsafe-inline'` (chart.tsx umstellen oder Nonce) | A05 | M | Mittel | P1 |
| 6 | LLM-Fehler nicht mehr im Client-Detail leaken           | A09 | XS | Mittel | P1 |
| 7 | `metrics_allowed_ips` mit CIDR-Support                   | A05 | XS | Niedrig | P1 |
| 8 | Logout ruft `verify_csrf` (Defense-in-Depth)             | A07 | XS | Niedrig | P1 |
| 9 | `npm update postcss`, `npm audit` in PR-Report           | A06 | XS | Niedrig | P2 |
| 10 | `# nosec B608` an statischen SQL-Fragments              | A03 | XS | Niedrig (Rauschen) | P2 |
| 11 | `secrets.SystemRandom().uniform` für Webhook-Jitter      | A02 | XS | Niedrig | P2 |
| 12 | Defense-in-Depth-Asserts gegen Default-User in non-dev   | A04 | XS | Niedrig | P2 |
| 13 | HSTS `preload` + `includeSubDomains`                     | A05 | XS | Niedrig | P3 |
| 14 | `value_preview`-Logging hashen statt Klartext            | A09 | S  | Niedrig | P3 |
| 15 | `docs_url` zusätzlich an `app_environment` koppeln       | A05 | XS | Niedrig | P3 |
| 16 | OIDC-Discovery cachen                                   | A05 | S  | Niedrig | P3 |
| 17 | Default-User per `ON CONFLICT DO NOTHING`                | A04 | XS | Niedrig | P3 |

---

## Empfohlene weitere Maßnahmen (außerhalb Top-10-Klassifikation)

- **Threat Model dokumentieren**: Spezifisch fürs DSGVO-Tool ein kurzes Bedrohungsmodell (Tenant-Isolation, DSAR-Vertraulichkeit, AVV-Daten, Webhook-Empfänger), z. B. unter `docs/security-threat-model.md`. Es macht künftige Reviews effizienter.
- **`bandit -ll` (low confidence) gelegentlich manuell** durchgehen; die wöchentliche CI fährt nur Medium+.
- **DAST/Funktionstests gegen API**: ein leichter ZAP- oder Schemathesis-Lauf gegen die generierte OpenAPI-Spezifikation deckt Edge-Cases (Header-Smuggling, Pagination-Limits, IDOR) effizient ab.
- **Secrets-Rotation-Playbook** für `WEBHOOK_SECRET_ENCRYPTION_KEY` (Fernet unterstützt MultiFernet) – aktuell undokumentiert.
- **Audit-Log-Authentizität**: ActivityLog ist heute reine DB-Zeile; Hash-Kette / Append-Only-View für Behördennachweis erwägen.

---

## Reproduktion der Toolausgaben

```bash
# Bandit
bandit -r backend/app/ -f json -o bandit-report.json
bandit -r backend/app/ --severity-level low --confidence-level low

# pip-audit (benötigt Internet)
pip-audit -r backend/requirements.txt

# npm audit
npm audit --json

# Semgrep (siehe .github/workflows)
semgrep --config=p/python --config=p/secrets --config=p/owasp-top-ten backend/app/
```
