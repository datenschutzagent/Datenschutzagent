# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Added
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
- Backend codebasisweit mit der konfigurierten Toolchain bereinigt
  (`ruff --fix` + `black`): Import-Sortierung/-Gruppierung, Entfernen ungenutzter
  Importe, Modernisierungen (`datetime.UTC`, `X | Y`-Isinstance), konsistente
  Formatierung. Verhalten unverändert.

### Fixed
- **Latenter Bug in `/metrics`**: `HTTPException` wurde im Endpoint verwendet,
  aber nie am Modulkopf importiert (`app/main.py`) — hätte bei deaktivierten
  Metriken bzw. nicht erlaubter IP einen `NameError` statt 404/403 ausgelöst.
  Vom neuen Ruff-Gate aufgedeckt und behoben.
- Exception-Chaining (`raise ... from`) in API-Fehlerpfaden ergänzt (B904).

### Notes
- Die Frontend-Typprüfung (`tsc --noEmit`) und ESLint sind noch nicht als
  blockierende CI-Gates aktiv; die bestehenden Typ-/Lint-Befunde werden in einer
  Folgearbeit auf null gebracht.
