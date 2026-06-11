# Security Policy

DatenschutzAgent verarbeitet potenziell sensible, personenbezogene Daten (DSGVO).
Sicherheitslücken nehmen wir entsprechend ernst.

## Eine Schwachstelle melden

Bitte melden Sie Sicherheitslücken **nicht über öffentliche GitHub-Issues**.

Stattdessen:

- Nutzen Sie **GitHub Security Advisories** („Report a vulnerability" im Tab
  *Security* dieses Repositories), oder
- senden Sie eine E-Mail an das Maintainer-Team (Kontakt siehe Repository-Profil
  bzw. `CONTRIBUTING.md`).

Bitte geben Sie an:

- betroffene Komponente/Version (Backend, Frontend, Container),
- Beschreibung und möglichst eine Reproduktion (Proof of Concept),
- erwartete Auswirkung (z. B. Datenabfluss, Rechteausweitung).

Wir bestätigen den Eingang in der Regel innerhalb von **5 Werktagen** und halten
Sie über den Fortschritt auf dem Laufenden. Bitte gewähren Sie eine angemessene
Frist zur Behebung, bevor Sie Details veröffentlichen (Coordinated Disclosure).

## Unterstützte Versionen

Sicherheitsupdates werden für den `main`-Branch bereitgestellt. Es gibt derzeit
keine Long-Term-Support-Branches.

## Sicherheitsmaßnahmen im Projekt

Automatisierte Prüfungen laufen in CI (siehe `.github/workflows/security.yml`):

- **Bandit** – Python SAST
- **pip-audit** / **npm audit** – bekannte CVEs in Abhängigkeiten
- **Semgrep** – OWASP Top 10 + Secret-Patterns
- **Trivy** – Container-Schwachstellen-Scan
- **detect-secrets** – Secret-Scanning mit Baseline

Zusätzlich erzwingen Pre-Commit-Hooks (`.pre-commit-config.yaml`) Lint,
Formatierung und Secret-Erkennung lokal; CI erzwingt Lint/Format/Tests serverseitig.
