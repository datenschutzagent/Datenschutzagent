# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Added (Runde 3 – Frontend und Tests)
- **Frontend-Coverage-Gate:** `npm run test:coverage` (`@vitest/coverage-v8`,
  Konfiguration in `vite.config.ts`, nur App-Code) mit Ratchet-Schwellen knapp
  unter dem Messwert (29 % Zeilen); lcov-Artefakt in CI. Neue Tests für
  `useMultiStepForm`, `AuthContext`, `CaseDetailContext` (je 100 % Zeilen), die
  `tom-page` und die Key-Factories der Katalog-Seiten (202 statt 111 Tests).
- **Backend-Tests** für die schwächsten Module (`mitigations`, `cases/checks`,
  `playbooks`, `admin_prompt_templates`, `legal_bases`, `case_templates`,
  `exports`, `cases/vvt`, `annotated_document_service`, `org_profile_loader`,
  `cli`); Factory-Helfer in `tests/factories.py`, Marker `requires_db`
  (automatisch für `client`-Tests, ohne `DATABASE_URL` übersprungen), ein
  echter 429-Test mit aktivem Limiter. `.coveragerc` mit
  `concurrency = greenlet,thread` – ohne diese Einstellung verlor coverage in
  jedem async Handler alle Zeilen nach dem ersten `await db.execute()`, die
  bisherigen Zahlen für DB-Routen waren systematisch zu niedrig. Gate von 63 %
  auf 77 % angehoben (gemessen 78,3 %).
- **Evals:** `python -m evals.run --strict` lässt eine angeforderte, aber nicht
  lauffähige Suite (`--llm`/`--ocr`) fehlschlagen statt still zu warnen;
  `--out FILE` schreibt die Zusammenfassung als JSON. Neuer Workflow
  `nightly.yml`: Offline-Evals als Artefakt, LLM-Evals nur bei konfiguriertem
  `NIGHTLY_LLM_PROVIDER`/`NIGHTLY_LLM_API_KEY`, sowie die vollständige
  Playwright-Suite gegen den Docker-Stack.
- **Bundle-Größe als CI-Artefakt** (`scripts/bundle-size.mjs`), alle Routen per
  `React.lazy` (Initial-Chunk 2,5 MB → 210 kB), eine ErrorBoundary je Route.

### Changed (Runde 3 – Frontend und Tests)
- **Katalog-Seiten `dsr`, `tom`, `avv`, `data-breaches`** laden über TanStack
  Query mit Key-Factories (`lib/queries/*Queries.ts`); Mutationen invalidieren
  statt lokal nachzuziehen, Ladefehler werden mit „Erneut versuchen“ angezeigt.
- **Fehler sichtbar:** 32 leere `catch {}` zeigen jetzt die Ursache aus
  `ApiError` als Toast-Beschreibung (`lib/errors.ts`), drei weitere loggen.
- **A11y-Regeln als Fehler:** `label-has-associated-control`,
  `click-events-have-key-events`, `no-static-element-interactions`; 77 Treffer
  behoben (Labels mit `htmlFor`, `DialogDescription`, Tastaturbedienung für
  klickbare Karten/Zeilen).
- **Aufgeräumt:** Label-/Farb-Maps nach `lib/labels.ts`, `mock-data.ts` und
  der Mock-Fallback im Dashboard entfernt; 24 ungenutzte Dependencies
  (u. a. `msw`, `date-fns`, `motion`, `react-dnd`) und 20 nie importierte
  `components/ui`-Dateien gelöscht.
- **E2E:** Testdaten werden per API angelegt statt „erster Vorgang, falls
  vorhanden“; harte Assertions statt `.catch(() => {})`; `data-testid` an
  Vorgangs-Karten, Tabs und Upload; `retries: 1`; das `@smoke`-Set läuft im
  PR-Gate, die volle Suite nightly.

### Fixed (Runde 3)
- `POST /case-templates/apply` und `POST /cases/{id}/run-checks` mit einem
  Playbook ohne Checks antworteten 500 (`MissingGreenlet`: `db.refresh()`
  verwarf die eager geladenen Relationen, das Antwortmodell lud `findings`
  dann lazy). Beide Stellen laden den Vorgang jetzt neu mit `case_relations()`.
- Die Eval-Schwelle `VVTFieldRecall` hatte keinen Evaluator mehr und gatete
  nichts; entfernt, ein Test prüft die Zuordnung Schwelle → Evaluator.
- **Dokument-Upload im Docker-Stack** (`STORAGE_BACKEND=local`, Standard):
  `/app/storage` fehlte im Image (`.dockerignore`), das benannte Volume
  `backend_storage` wurde daher root-eigen angelegt und jeder Upload endete mit
  `Permission denied` (500). Das Verzeichnis wird jetzt im Image mit
  `appuser`-Besitz angelegt. Gefunden durch die neuen E2E-Tests; bestehende
  Installationen mit bereits angelegtem Volume müssen es einmalig neu anlegen
  (`docker compose down -v` bei leerem Speicher) oder den Besitzer ändern.

### Security
- **Audit-Log hash-verkettet und um Lesezugriffe erweitert** (Phase 1, S6):
  `api_audit_log` bekommt `seq`, `prev_hash`, `entry_hash`, `resource_id`
  (Migration `d0e1f2a3b4c5`). Lesezugriffe auf Dokumentinhalte/Downloads,
  annotierte Dokumente, DSB-Reports und Exporte werden mit Objekt-ID
  protokolliert. Schreibfehler zählt `api_audit_log_write_failures_total`;
  `AUDIT_LOG_STRICT=true` antwortet dann mit 500. Prüfung:
  `python -m app.cli audit verify`.
- **Upload-Härtung** (S4): ZIP-Container von DOCX/XLSX/PPTX werden vor dem Parsen
  auf entpackte Größe, Eintragszahl und Kompressionsverhältnis geprüft
  (Zip-Bomben); PDFs über `MAX_PDF_PAGES` werden abgelehnt; OOXML-Teile werden
  mit gehärtetem lxml-Parser gelesen (keine externen Entities, kein Netz).
- **Session-Lebensdauer begrenzt** (S5): `SESSION_ABSOLUTE_TTL_SECONDS`
  (Standard 8 h) deckelt die gleitende Session; alle Sessions eines Nutzers
  werden bei Rollenänderung widerrufen. Sessions ohne `issued_at` (vor diesem
  Release) erfordern einmalig eine neue Anmeldung.
- **Key-Rotation für Webhook-Secrets** (S7): `WEBHOOK_SECRET_ENCRYPTION_KEY`
  akzeptiert eine kommagetrennte Schlüsselliste (MultiFernet); in production ist
  ein nicht entschlüsselbarer Wert ein Fehler statt eines stillen
  Klartext-Fallbacks. `rotate_secret()` schlüsselt Bestand um.
- **Keine PII in Logs** (S8): Benachrichtigungs-Events speichern
  `recipient_user_id` statt E-Mail; die Prompt-Injection-Warnung enthält keinen
  Inhaltsauszug mehr.
- **Finding-Chat gehärtet** (S9): Nutzer-Nachrichten, Verlauf und Dokumentauszug
  laufen in Content-Markern, System-Prompt mit Safety-Preamble.
- **Ausgehende URLs validiert** (S10): `OIDC_ISSUER_URL`, `OLLAMA_BASE_URL`,
  `OCR_BASE_URL`, `LLM_BASE_URL`, `WEAVIATE_URL` nur `http(s)://`, mit Host,
  ohne Credentials/Fragment; `OIDC_ISSUER_URL` in production nur `https://`.
- **`TRUSTED_PROXIES` ist in production Pflicht** (Qualitätsplan Phase 1, S1).
  Ohne den Wert teilen sich hinter dem Reverse-Proxy alle Clients einen
  Rate-Limit-Bucket; der Start wird jetzt verweigert statt nur zu warnen.
- Uvicorn startet mit `--proxy-headers --forwarded-allow-ips=$TRUSTED_PROXIES`
  (S2): `X-Forwarded-Proto`/`X-Forwarded-For` werden nur von den konfigurierten
  Proxies akzeptiert; hinter TLS-Terminierung ist `request.url.scheme` jetzt `https`.
- **Externe LLM-Provider brauchen eine DSGVO-Freigabe** (S3):
  `LLM_PROVIDER=openai|anthropic` erfordert `LLM_EXTERNAL_TRANSFER_ACKNOWLEDGED=true`
  (production: Startabbruch, sonst Warnung). Jeder Start loggt die Übermittlung;
  der Admin-Bereich zeigt Provider und Freigabestatus unter „System“.

### Changed (Phase 2 – Backend-Robustheit)
- **Abhängigkeiten/Image (aus dem CI-Lauf des PR):** pydantic-ai und
  pydantic-evals auf 1.106.0 (PYSEC-2026-2977/-3692); npm-Lockfile per
  `npm audit fix` (undici, react-router, postcss, js-yaml, nanoid,
  brace-expansion). Das Backend-Image enthält kein pip mehr – zur Laufzeit
  installiert niemand Pakete, und pips mitgelieferte SBOM meldete seine
  privaten msgpack/setuptools-Kopien als Image-Schwachstellen.
- **E2E-Smoke** an den dreistufigen „Neuer Vorgang“-Dialog angepasst (der Test
  suchte einen nicht mehr existierenden „Erstellen“-Button und war auch auf
  `main` rot).
- **mypy für `app/core` und `app/services`** in Pre-Commit und CI (`mypy.ini`,
  Baseline auf null gebracht). Dabei gefunden: der MinIO-Verbindungscheck
  importierte eine nicht existierende Funktion und meldete den Speicher immer
  als „unreachable“; `Agent(output_retries=…)` war in pydantic-ai 1.99
  deprecated (jetzt `retries={"output": …}`).
- **Event-Loop bleibt frei:** OIDC-Discovery/Token-Exchange über `httpx.AsyncClient`,
  SMTP-Versand, Storage-IO, Textextraktion und Weaviate-Abfragen laufen in
  Worker-Threads; der Legal-Basis-Kontext wird pro Prüflauf einmal je Check
  geladen statt je Check × Dokument.
- **Celery-Fehlerpolitik:** Tasks liefern kein `{"ok": false}` mehr als SUCCESS.
  Transiente Fehler (Storage/Netz/DB/LLM-Provider) werden mit Backoff
  30/120/300 s bis zu 3× wiederholt, alles andere markiert den Job FAILED und
  wird als Celery-FAILURE gezählt.
- **Fehlerantworten:** LLM-Ausfälle → 503 (`LLM_UNAVAILABLE`,
  `LLM_RETRY_EXHAUSTED`, `LLM_BUDGET_EXCEEDED`), Prompt-Injection → 400
  (`PROMPT_REJECTED`); unerwartete Fehler → 500 ohne interne Details, mit
  `request_id` zum Nachschlagen im Log.
- **LLM-Kosten:** nur transiente Provider-Fehler werden wiederholt, der
  Circuit-Breaker zählt jeden Fehlversuch, `RUN_CHECKS_MAX_LLM_CALLS`
  (Standard 1000) deckelt die Provider-Aufrufe je Prüflauf; das Activity-Log
  enthält `llm_calls` und `llm_budget_exhausted`.
- **Datenzugriff:** Beat-Recheck lädt Playbooks einmal statt je Vorgang; der
  CSV-Export zählt offene Befunde in SQL; `GET /documents` und
  `GET /cases/{id}/activities` sind paginiert (`skip`/`limit`);
  `documents(case_id, type, version)` ist UNIQUE (Migration `e1f2a3b4c5d6`,
  Altbestand mit Duplikaten wird umnummeriert), der Upload wiederholt bei
  Versionskollision statt 500.
- **Bulk-Upload** isoliert jede Datei in einem Savepoint; ein Parser- oder
  Storage-Fehler einer Datei lässt die übrigen intakt.
- Kein stilles `except: pass` mehr (Metrik-Gauges, Charset-Erkennung,
  VVT-Vollständigkeit im DSB-Report loggen ihre Ursache); Ruff BLE001 gilt
  jetzt auch für alle Routen (Fehlergrenzen tragen inline `noqa` mit Grund).
- **Zerlegung der komplexesten Funktionen** (Ruff C901 ≤ 15 gilt jetzt ohne
  Ausnahmen): `scan_and_notify_deadlines` ist eine generische
  Benachrichtigungsschleife plus sechs Nachrichten-Builder; die vier
  Kopien `_doc_check_*`/`_case_check_*` sind ein `_execute_check` mit
  Ziel-Objekt (Dokument/Vorgang) und Strategie (full_text/rag inkl.
  Fallback); `run_checks_impl`, `pipeline_stats` und `generate_dsfa` sind in
  benannte Schritte aufgeteilt. Risiko-Score-Historie und Ähnlichkeits-Ranking
  liegen in `case_risk_service`, der DOCX-Export in `findings_export_service`
  (CSV und DOCX teilen sich die Label-Maps). Verhalten unverändert, jetzt mit
  reinen Unit-Tests je Baustein; Backend-Coverage 65 %, Gate auf 63 % angehoben.

### Added
- **CI-Gates (Qualitätsplan Phase 0):** Frontend `tsc --noEmit` und
  `eslint --max-warnings=0` blockieren jetzt; Alembic-Gate (`upgrade head`,
  `alembic check`, Downgrade/Upgrade-Roundtrip); Semgrep bricht bei
  ERROR-Findings ab; detect-secrets prüft gegen die eingecheckte
  `.secrets.baseline`; abgelaufene `.trivyignore`-Ausnahmen machen den Scan rot;
  `timeout-minutes` und `concurrency` in beiden Workflows; Coverage-Gate 58 %
  mit XML-Artefakt; Ruff `C901` (max-complexity 15) mit per-file-Ausnahmen für
  die vier bekannten Altlasten.
- `mkdocs/docs/projekt/qualitaetsplan.md`: Analyse aus vier Perspektiven und
  priorisierter Maßnahmenplan.
- CI-Gates für das Backend: `ruff` (Lint) und `black --check` (Formatierung)
  laufen jetzt in GitHub Actions (`test.yml`), zusätzlich Test-Coverage-Reporting
  (`pytest --cov`).
- `.github/dependabot.yml`: wöchentliche, gruppierte Dependency-Updates für pip,
  npm und GitHub Actions.
- Projekt-Meta-Dateien: `SECURITY.md` (Disclosure-Policy), `CONTRIBUTING.md`
  (Setup & Gates), `CHANGELOG.md`, `CLAUDE.md`.
- Frontend-Tooling: `typescript`, `@types/react`, `@types/react-dom` als
  devDependencies und `npm run typecheck`-Skript (Vorbereitung der Typprüfung).

### Changed
- Die Anwendung legt beim Start keine Tabellen mehr per `create_all` an; Alembic
  ist die einzige Schemaquelle (Tests bauen ihr Schema weiterhin per `init_db`).
  `UserModel` deklariert den partiellen Unique-Index `ix_users_oidc_sub`, den die
  Baseline-Migration anlegt – vom neuen `alembic check` sofort als Drift erkannt.
- `GET /cases/export` akzeptiert `deadline_overdue` und nutzt denselben
  Filter-Builder wie `GET /cases`.
- `app/api/routes/cases.py` (god-file, ~1.4k Zeilen, 26 Routen) in ein Paket
  `app/api/routes/cases/` aufgeteilt: `crud.py` (Kern-CRUD), `checks.py`
  (run-checks), `vvt.py` (VVT-Normalisierung). Pfade und Registrierungsreihenfolge
  unverändert (per Decorator-Vergleich gegen HEAD verifiziert).
- Backend codebasisweit mit der konfigurierten Toolchain bereinigt
  (`ruff --fix` + `black`): Import-Sortierung/-Gruppierung, Entfernen ungenutzter
  Importe, Modernisierungen (`datetime.UTC`, `X | Y`-Isinstance), konsistente
  Formatierung. Verhalten unverändert.

### Fixed
- **Cookie-Login (`POST /auth/session`)** rief den asynchronen JWT-Verifier ohne
  `await` auf: jeder Login endete mit 500 und die Signatur wurde nie geprüft.
- `POST /admin/webhooks/{id}/test` entpackte drei statt vier Rückgabewerte → 500.
- CSV-Export interpretierte `has_open_findings` als „hat ein Dokument“.
- `PATCH /findings/bulk-update` zählte unveränderte Findings als aktualisiert.
- DSB-Report, DSFA und periodischer Re-Check dispatchten den Celery-Task vor
  dem Commit; der Worker fand die Job-Zeile nicht.
- `LLM_REQUEST_TIMEOUT` galt nur für Ollama, nicht für OpenAI/Anthropic.
- VVT-Normalisierung verwarf harmlosen Fachtext („act as a …“) bei
  `PROMPT_INJECTION_BLOCK=true`; Dokumenttext wird jetzt wie in den Checks in
  Marker eingeschlossen statt durch den Feld-Sanitizer geschickt.
- Findings-DOCX: Statuszähler wurde berechnet, aber nicht ausgegeben.
- `POST /cases` persistierte `deadline` nicht.
- Frontend: 81 TypeScript-Fehler und 44 ESLint-Befunde behoben (typisierte
  API-Mapper, echte Null-Guards statt `!`, korrekte `useEffect`-Abhängigkeiten);
  `dsb-report-view` rendert während laufender Generierung nicht mehr in einen
  Null-Zugriff.
- **Latenter Bug in `/metrics`**: `HTTPException` wurde im Endpoint verwendet,
  aber nie am Modulkopf importiert (`app/main.py`) — hätte bei deaktivierten
  Metriken bzw. nicht erlaubter IP einen `NameError` statt 404/403 ausgelöst.
  Vom neuen Ruff-Gate aufgedeckt und behoben.
- Exception-Chaining (`raise ... from`) in API-Fehlerpfaden ergänzt (B904).
