# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

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
