# Qualitätsplan – Analyse und Maßnahmen

Stand: September 2026, Commit `84ba891`. Grundlage: vier unabhängige Reviews
(Backend-Architektur, Frontend, Tests/CI/Betrieb, Security/DSGVO) plus Messungen
mit den echten Werkzeugen (`pytest --cov`, `tsc`, `eslint`, `ruff`, `black`, `vitest`).
Jeder Befund ist mit Datei und Zeile belegt; nichts hier ist geschätzt.
Zeilenangaben beziehen sich auf den Analyse-Commit; nach Phase 0 haben sich einige
verschoben.

## 0. Umsetzungsstand

| Phase | Status | Ergebnis |
| :--- | :--- | :--- |
| 0 – Bugs + Gates | **erledigt** (2026-09-05) | B1–B9 behoben, je mit Regressionstest (724 Tests, Coverage 59,9 %). G1–G7 aktiv. Frontend: `tsc` 0 Fehler, ESLint 0/0. Der neue `alembic check` fand sofort einen Drift (partieller Index `ix_users_oidc_sub` fehlte im Modell). |
| 1 – Security/DSGVO | **erledigt** (2026-09-05) | S1–S10 umgesetzt, je mit Tests: Proxy-Vertrauen erzwungen, DSGVO-Freigabe für externe LLM-Provider, Zip-Bomben-/XXE-/PDF-Limits, absolute Session-Lebensdauer + Widerruf bei Rollenwechsel, hash-verkettetes Audit-Log mit Lesezugriffen und `audit verify`, MultiFernet-Rotation, PII aus Logs, Finding-Chat in Markern, URL-Validatoren. Bewusst nicht umgesetzt: Sperre privater IP-Ranges (S10) – Ollama/Weaviate liegen legitim im LAN/Docker-Netz. |
| 2 – Backend-Robustheit | offen | – |
| 3 – Frontend | offen | F1 (Typfehler) wurde für G1 vorgezogen und ist erledigt. |
| 4 – Tests/Evals | offen | – |
| 5 – Betrieb/Doku | offen | – |

Entscheidung zu 4.1 (Mandantentrennung): **Single-Org**, siehe Abschnitt 4.

Korrekturen gegenüber der Erstanalyse, beim Umsetzen festgestellt:

- **Bandit gatete bereits.** Bandit beendet sich auch mit `--format json` mit Exit 1,
  sobald ein Finding vorliegt (lokal verifiziert). Nur Semgrep (kein `--error`) und
  detect-secrets (keine Baseline) waren wirkungslos. Zielwert "Security-Scanner gatend"
  war also 4 von 6, nicht 3 von 6.
- **`temporalio` ist eine transitive Abhängigkeit** (installiert, nicht in
  `requirements.txt`). Die Trivy-Ausnahme war trotzdem obsolet: temporalio 1.32.0
  bringt pyo3 0.29.0 mit dem Fix. Eintrag entfernt, Ablauf-Check in CI.
- **B9 (neu):** `POST /cases` akzeptierte `deadline` im Schema, persistierte es aber
  nicht (`crud.py`, `CaseModel(...)` ohne `deadline=`). Beim Test zu B3 aufgefallen.

---

## 1. Ist-Stand in Zahlen

| Metrik | Wert | Bewertung |
| :--- | :--- | :--- |
| Backend-Code | 117 Dateien, ~27 000 Zeilen, 24 Route-Module, 36 Services | – |
| Backend-Tests | 56 Dateien, 704 Tests, alle grün, 19 s Laufzeit | gut |
| Backend-Coverage (gemessen) | **58 %** (Gate: 55 %) | Routen 25–49 %, Services stark gemischt |
| Ruff / Black (CI-Versionen) | 0 Befunde | gut |
| Frontend-Code | 147 Dateien, ~40 000 Zeilen (10 161 davon generiertes Schema) | – |
| Frontend-Tests | 15 Dateien, 106 Tests, alle grün | Coverage nicht messbar (kein Reporter installiert) |
| `tsc --noEmit` | **81 Fehler** in 12 Dateien | **wird in CI nicht geprüft** |
| `eslint src` | **8 Errors, 36 Warnings** | **wird in CI nicht geprüft** |
| E2E in CI | 2 von 8 Playwright-Tests (`@smoke`) | 7 Assertions sind per `.catch(() => false)` optional |
| Statische Typprüfung Backend | keine (kein mypy/pyright) | Lücke |
| Alembic | 9 Revisionen, lineare Kette, alle mit `downgrade()` | gut, aber kein Drift-Check |

Die Basis ist solide: typisierte ORM-Modelle, RFC-7807-Fehlerformat, vollständige
Security-Header, Prompt-Härtung, SHA-gepinnte Actions, Dependabot, ein Offline-Eval-Gate.
Die Qualitätsprobleme liegen weniger in "schlechtem Code" als in **fehlenden Gates**
(Frontend, Typen, Migrationen, Security-Scanner) und in einigen **echten Bugs**, die
genau deshalb unbemerkt geblieben sind.

---

## 2. Grundsätze für den Plan

1. **Gates vor Refactoring.** Erst die Prüfungen scharf schalten, dann aufräumen.
   Sonst wächst der Fehlerberg während des Aufräumens weiter (das ist beim Frontend
   nachweislich passiert: 81 Typfehler bei `strict: true`).
2. **Ratchet statt Zielwert.** Coverage-Schwellen werden nach jedem Merge auf den
   erreichten Stand angehoben, nie gesenkt. Kein Sprint "auf 90 %".
3. **Bugs vor Struktur.** Verifizierte Fehlfunktionen (Abschnitt 3.1) haben Vorrang
   vor jeder Architekturmaßnahme.
4. **Kleine, reviewbare PRs.** Jede Maßnahme unten ist so geschnitten, dass sie ein
   eigener PR mit eigenem Test sein kann.

---

## 3. Maßnahmen nach Phasen

### Phase 0 – Sofort (1 Woche): Bugs beheben, Gates einziehen

#### 3.1 Verifizierte Bugs

| # | Bug | Beleg | Fix |
| :--- | :--- | :--- | :--- |
| B1 | **Cookie-Login ist tot.** `_verify_jwt` ist `async`, wird aber ohne `await` aufgerufen. `claims` ist eine Coroutine, `.get("sub")` wirft `AttributeError` → 500. Die Signaturprüfung läuft nie. | `backend/app/api/routes/auth.py:181`, `backend/app/core/auth.py:152` | `await` ergänzen; Negativtest: `POST /auth/session` mit gefälschtem `id_token` muss 401 liefern. Aktuell gibt es keinen Test für diesen Pfad. |
| B2 | **Webhook-Test-Endpunkt wirft 500.** Route entpackt 3 Werte, `_deliver_webhook` liefert 4. | `backend/app/api/routes/webhooks.py:245`, `backend/app/services/webhook_service.py:159-183` | Vierten Wert (`attempts`) entgegennehmen; API-Test für `POST /admin/webhooks/{id}/test`. |
| B3 | **CSV-Export filtert falsch.** `has_open_findings` prüft im Export auf *Existenz eines Dokuments*, in der Liste auf offene Findings. Export und Liste liefern verschiedene Zeilen. | `backend/app/api/routes/cases/crud.py:330-337` vs. `:149-204` | Gemeinsamen `CaseQuery`-Builder extrahieren, beide Endpunkte darauf umstellen; Test, der Liste und Export mit gleichem Filter vergleicht. |
| B4 | **Bulk-Status meldet falsche Anzahl.** `updated += 1` steht außerhalb des `if finding.status != body.status`. | `backend/app/api/routes/findings.py:298-313` | Zähler in den `if`-Block ziehen (vgl. korrekte Variante `crud.py:273-281`). |
| B5 | **Celery-Task wird vor dem Commit dispatcht.** Worker findet die Job-Zeile nicht. In `checks.py:277-279` bereits behoben, an drei Stellen nicht. | `crud.py:846-850` (DSB-Report), `dsfa.py:113-120`, `celery_app.py:846-855` | `await db.commit()` vor `.delay()`, wie in `checks.py`. |
| B6 | **LLM-Timeout gilt nicht für OpenAI/Anthropic.** Config-Doku behauptet "alle Provider", der `httpx`-Client mit Timeout wird nur an Ollama übergeben. | `backend/app/core/llm.py:342,361` vs. `config.py:243-248` | `http_client` an beide Provider durchreichen; Test mit gemocktem Provider, der den Timeout prüft. |
| B7 | **VVT-Normalisierung bricht bei harmlosem Fachtext ab.** Dokumenttext läuft durch `sanitize_prompt_field()` statt `wrap_untrusted_content()`; bei `prompt_injection_block=true` (Default) löst z. B. "act as a" eine `PromptInjectionError` aus. | `backend/app/services/vvt_service.py:377` vs. korrekt in `check_runner.py:449` | Auf `wrap_untrusted_content` umstellen; Regressionstest mit Blocklist-Wort im Dokumenttext. |
| B8 | **Toter Ausdruck** – Statuszähler wird berechnet und verworfen. | `backend/app/api/routes/findings.py:365` | In die Zusammenfassungstabelle aufnehmen oder entfernen. |
| B9 | **`deadline` geht beim Anlegen verloren.** `CaseCreate.deadline` ist im Schema, `create_case` übergibt es nicht ans Modell. | `backend/app/api/routes/cases/crud.py` (`create_case`) | `deadline=body.deadline`; Test, der die Frist nach dem Anlegen zurückliest. |

#### 3.2 CI-Gates

| # | Maßnahme | Beleg der Lücke |
| :--- | :--- | :--- |
| G1 | `npm run typecheck` und `npm run lint -- --max-warnings=0` als Steps im `frontend`-Job. Vorher die 81 TS- und 8 ESLint-Fehler beheben (siehe Phase 3, F1). | `.github/workflows/test.yml:9-22` führt nur `npm run test` aus. `CONTRIBUTING.md:49-50` und `CHANGELOG.md:37-40` nennen das als bekannt offen. |
| G2 | `alembic upgrade head && alembic check` gegen den Postgres-Service in CI; danach `init_db()`/`create_all` aus dem Produktions-Lifespan entfernen (nur noch in Tests). Heute existieren zwei Schemaquellen: Entrypoint fährt Alembic, Lifespan ruft zusätzlich `create_all` → neue Tabellen entstehen ohne Migration, Drift bleibt unsichtbar. | `backend/entrypoint.sh:7`, `backend/app/main.py:106`, `backend/app/database.py:56-63`; widerspricht `CONTRIBUTING.md:61`. |
| G3 | Semgrep gatend machen (`--error`, zunächst Severity ERROR), `.secrets.baseline` erzeugen und einchecken. Semgrep schrieb nur ein JSON-Artefakt; der detect-secrets-Step lief mangels Baseline immer in den `else`-Zweig mit Exit 0, und `pre-commit run --all-files` schlug am fehlenden Baseline-File fehl. (Bandit gatete bereits, siehe Abschnitt 0.) | `.github/workflows/security.yml:78-91,180-188`; `.pre-commit-config.yaml:43-47` |
| G4 | `timeout-minutes` (20/20/30) und `concurrency` mit `cancel-in-progress` in beiden Workflows. | keine Treffer in `test.yml`/`security.yml` |
| G5 | Coverage-Gate von 55 auf 58 anheben, `--cov-report=xml` als Artefakt; Ratchet-Regel in `CONTRIBUTING.md` festhalten. | `test.yml:65-67` |
| G6 | Ruff `C901` mit `max-complexity=15` aktivieren. Trifft heute genau 4 Funktionen (`scan_and_notify_deadlines` 36, `run_checks_impl` 24, `pipeline_stats` 18, `generate_dsfa` 16); per-file-ignore für diese vier bis zur Zerlegung in Phase 2. | `backend/ruff.toml:7-18` |
| G7 | `.trivyignore`-Eintrag für `temporalio` entfernen: die referenzierte Schwachstelle ist in der installierten Version (1.32.0, pyo3 0.29.0) behoben; die Ausnahme wäre am 14.09.2026 abgelaufen. Kleiner CI-Step, der abgelaufene `Expires:`-Zeilen rot macht. | `.trivyignore:6-13` |

### Phase 1 – Sicherheit und Datenschutz (2–3 Wochen)

Sortiert nach Risiko. S1–S3 sind Konfigurations- und Kleinänderungen, S4–S7 brauchen
je einen eigenen PR mit Tests.

| # | Maßnahme | Befund | Beleg |
| :--- | :--- | :--- | :--- |
| S1 | `TRUSTED_PROXIES` in Produktion **erzwingen** statt warnen. | Hinter dem mitgelieferten Nginx ist `request.client.host` die Proxy-IP; alle Clients teilen sich einen Rate-Limit-Bucket. 10 Login-Versuche/Minute gelten damit global, nicht pro Angreifer. | `backend/app/config.py:92,635-640`, `core/rate_limit.py:51-68`, `nginx.conf:24-26` |
| S2 | Uvicorn mit `--proxy-headers --forwarded-allow-ips` starten. | `request.url.scheme` bleibt hinter Nginx `http`. | `backend/entrypoint.sh:10` |
| S3 | Warnung + explizites Flag (`LLM_EXTERNAL_TRANSFER_ACKNOWLEDGED`) beim Start, wenn `LLM_PROVIDER` nicht lokal ist. | Dokumentvolltexte gehen an externe Anbieter; `anthropic_prompt_caching=True` per Default; kein Hinweis im Log. Für ein DSGVO-Tool ist das ein Glaubwürdigkeitsproblem. | `core/llm.py:334-365`, `config.py:206,376-386` |
| S4 | Dekomprimierungs-Limits vor dem Parsen von DOCX/XLSX/PPTX (`zipfile.infolist()`: Gesamtgröße, Eintragszahl, Ratio); Seitenlimit für PDF außerhalb des OCR-Pfads; gehärteter lxml-Parser (`resolve_entities=False, no_network=True`). | Zip-Bomb mit 50-MB-Upload möglich; XXE-Vektor in Footnote-Parsing. | `services/document_processor.py:213,229,257,320`, `services/pdf_extractor.py` |
| S5 | Absolute Session-Lebensdauer (z. B. 8 h) zusätzlich zum gleitenden TTL; Session-Invalidierung bei Rollenänderung. | Sliding-TTL ohne Obergrenze: einmal ausgestelltes Cookie bleibt beliebig lange gültig. Cookie-Flags und CSRF sind korrekt. | `core/session.py:96-128,146-211` |
| S6 | Audit-Log: Lesezugriffe auf `documents/*/content` und `*/download` protokollieren; DB-Fehler in der Audit-Middleware nicht still schlucken; Hash-Kette (Vorgänger-Hash pro Zeile) für die dokumentierte "Unveränderbarkeit". | Heute nur mutierende Requests, fire-and-forget, normale Tabelle. | `main.py:452-486`, `models/_db/audit.py:18-24` |
| S7 | `MultiFernet` mit Key-Liste für Rotation; `decrypt_secret` außerhalb von Prod nicht still auf Klartext zurückfallen. | Nur ein Key, keine Rotation, manipulierter Key bleibt unbemerkt. | `core/crypto.py:22-41,75-82` |
| S8 | PII aus dem Activity-Log: `recipient: email` durch User-ID ersetzen; `value_preview` in der Prompt-Security-Warnung entfernen. | E-Mail-Adressen dauerhaft im Payload, Nutzerinhalt im Log. | `services/notification_service.py:173,226,291,347,421,582`, `core/prompt_security.py:121` |
| S9 | Chat-Nachricht in `finding_chat_service` durch `wrap_untrusted_content` schicken. | Unsanitisierter Nutzertext im Prompt. | `services/finding_chat_service.py:99,115` |
| S10 | SSRF-Validator für `oidc_issuer_url`, `ocr_base_url`, `ollama_base_url` in `config.py` (Schema, keine privaten Ranges außer explizit erlaubt). Webhooks sind bereits sauber. | Admin-konfiguriert, aber unvalidiert. | `routes/auth.py:47,88,132`, `services/ocr_service.py:33-59` |

### Phase 2 – Backend-Robustheit (3–4 Wochen)

| # | Maßnahme | Befund | Beleg |
| :--- | :--- | :--- | :--- |
| R1 | **Blockierende Aufrufe aus dem Event-Loop.** OIDC-Discovery/Token-Exchange auf `httpx.AsyncClient`; SMTP-Versand nach `asyncio.to_thread` oder in einen Celery-Task; Weaviate-Legal-Basis-Kontext pro Run cachen (läuft heute pro Check × pro Dokument neu). `save_file`/`get_file`/`extract_text` in Routen konsequent über `to_thread` (in `crud.py:599` bereits korrekt). | Bis zu 15 s Loop-Blockade pro Login; N Mails sequenziell in einer Admin-Route. | `routes/auth.py:104-135,177`, `routes/admin.py:223`, `services/run_checks_service.py:90-100,269,333,454,518`, `routes/documents.py:196,218,260,398,519` |
| R2 | **Celery-Fehlerbehandlung.** Die vier teuren Tasks fangen `Exception`, geben `{"ok": False}` zurück und enden als SUCCESS. Damit sind `acks_late`/`reject_on_worker_lost` wirkungslos, es gibt kein `autoretry_for`, und die Metrik zählt Fehlschläge als Erfolg. Fix: Status setzen, dann re-raisen; `autoretry_for` mit `max_retries`; Idempotenz-Guard für `RUNNING`-Jobs nach Worker-Crash. | | `celery_app.py:93-94,317-324,388-398,513-521,590-596,660-666` |
| R3 | **Exception-Handler für Domain-Fehler.** `LLMProviderError`/`LLMRetryExhaustedError` werden geworfen, aber nirgends gefangen; die ErrorCodes `LLM_UNAVAILABLE`/`LLM_RETRY_EXHAUSTED` sind toter Code. LLM-Ausfall wird generischer 500 statt 503. Zusätzlich 9 Stellen mit `detail=f"…: {exc}"`, die interne Fehlertexte an den Client geben. | | `core/exceptions.py:38-59`, `main.py:300-306`, `findings.py:712`, `crud.py:626` |
| R4 | **LLM-Kostenkontrolle.** Retry-Klassifikation (401/400/Schema-Fehler nicht wiederholen; Circuit-Breaker zählt erst nach Erschöpfung → 15 reale Requests bis Öffnen); Aufruf-Budget pro Job (heute stapeln sich `long_doc_max_chunks` × `self_consistency_n` × `output_retries` × `retry_attempts` unkontrolliert). Rückgabetyp von `get_active_model_name()` korrigieren (`None` landet im Cache-Key). | | `core/llm.py:250-267,388-390`, `services/check_runner.py:355-374,457-467`, `core/llm_cache.py:55` |
| R5 | **Statische Typprüfung.** mypy (oder pyright) in Pre-Commit und CI, zunächst `--ignore-missing-imports` und nur für `app/core`, `app/services`; Modul für Modul erweitern. Deckt R4 (Rückgabetyp), die `Mapped[str]`-vs-`nullable=True`-Inkonsistenzen und `bulk_update_cases(body: dict)` automatisch ab. | Kein Typchecker konfiguriert. | `_db/document.py:42`, `_db/job.py:32-36`, `crud.py:230-261` |
| R6 | **N+1 und Grenzen.** Beat-Task lädt alle Playbooks pro Case neu; `export_cases` lädt 5000 Cases mit Findings-Relation und zählt in Python; `list_documents` und `get_case_activities` haben keine Pagination. Unique-Constraint `(case_id, type, version)` gegen doppelte Dokumentversionen bei parallelem Upload. | | `celery_app.py:811-822`, `crud.py:341-363,417-422`, `documents.py:147-159,225-241` |
| R7 | **Zerlegung der vier komplexesten Funktionen** (aus G6): `scan_and_notify_deadlines` (383 Zeilen, 6 fast identische Scan-Blöcke → eine generische Scan-Funktion mit Konfigurationsliste), `run_checks_impl` + die vier `_doc_check_*`/`_case_check_*`-Varianten (360 Zeilen, ein Ablauf in vier Kopien → Strategie-Objekt), `pipeline_stats`, `generate_dsfa`. Risiko-Scoring und DOCX-Bau aus Routen in Services. | | `notification_service.py:105`, `run_checks_service.py:257-616,624`, `pipeline_service.py:37`, `dsfa_service.py:189`, `crud.py:915-1056`, `findings.py:339-414` |
| R8 | **Transaktionsgrenzen.** `get_db` committet am Request-Ende; trotzdem 11 explizite `commit()` in Routen, teils mitten in Update-Handlern. Regel festlegen (Commit nur in `get_db` oder nur in Services) und durchziehen. Bulk-Upload fängt nur `HTTPException` → Teilzustände. | | `database.py:44-54`, `documents.py:399,443,472-499`, `checks.py:279-282`, `legal_bases.py:74,118,142` |
| R9 | Silent-Swallows entfernen (4× `except Exception: pass`); BLE001-Ausnahmen in `ruff.toml` von 32 Dateien schrittweise reduzieren, beginnend mit `app/api/routes/cases/*`. | | `celery_app.py:70`, `main.py:414`, `document_processor.py:432`, `dsb_report_service.py:161`, `ruff.toml:35-79` |

### Phase 3 – Frontend (3–4 Wochen)

| # | Maßnahme | Befund | Beleg |
| :--- | :--- | :--- | :--- |
| F1 | **81 TS-Fehler und 8 ESLint-Errors beheben** (Voraussetzung für G1). Hauptquellen: `activity-timeline.tsx` (16, TS2678), `playbook-detail-page.tsx` (15, `normalizeChecks` castet `unknown` feldweise), `lib/api/playbooks.ts`/`documents.ts` (11, `Record<string, unknown>` statt API-Typ), TS7053 durch Indizierung von `Record<FindingSeverity,…>` mit `string`. | | `src/app/components/activity-timeline.tsx:39-81`, `src/app/pages/playbook-detail-page.tsx:58-68` |
| F2 | **Mock-Daten aus dem Produktionspfad.** `DashboardStats` rendert bei fehlendem Prop erfundene Fälle (`mockCases as unknown as ApiCase[]`, Doppel-Cast umgeht die Typprüfung). 13 Module importieren `mock-data.ts` (992 Zeilen), meist nur wegen Label-/Farb-Maps. Labels nach `lib/labels.ts` (aus API-Typen abgeleitet), Fixtures nach `__fixtures__`, Rest löschen. Das beseitigt zugleich die TS7053-Klasse aus F1. | | `src/app/components/dashboard-stats.tsx:54`, `src/app/lib/mock-data.ts` |
| F3 | **Fehler sichtbar machen.** 43 Stellen mit `} catch {` ohne Parameter werfen den `ApiError` (inkl. Status) weg; Nutzer sehen nur "konnte nicht geladen werden". `catch (e)` + `parseErrorResponse`-Message + Toast. `ErrorBoundary` pro Route statt nur global (heute reißt ein Render-Fehler in `tom-page` die ganze App). | | `src/app/pages/dsr-page.tsx:134-215`, `tom-page.tsx:131-236`, `avv-page.tsx:125-198`, `App.tsx:22` |
| F4 | **Serverstate auf TanStack Query.** Nur 7 Dateien nutzen Query; ~20 Seiten replizieren `useState`+`useEffect`+`load()` ohne Cache, Dedup oder Invalidierung. Zwei Stale-Closure-Bugs sind im Lint bereits sichtbar. Reihenfolge: `dsr`, `tom`, `avv`, `data-breaches` (strukturell identisch → gemeinsames "Katalog-Seite"-Muster), dann Insights. Key-Factories wie in `lib/queries/casesQueries.ts` als Standard; Invalidierung auf `casesKeys.all` statt nur den aktuellen Filter. | | `src/app/pages/playbook-detail-page.tsx:76-110`, `vvt-overview-page.tsx:103-111`, `cases-page.tsx:161`, `risk-mitigation-panel.tsx:69-83` |
| F5 | **Accessibility-Basis.** 60 `<Label>` ohne `htmlFor`; 28 klickbare Container ohne `role`/`tabIndex`/`onKeyDown`; 19 `DialogContent` mit nur 11 `DialogDescription`. `jsx-a11y` ist geladen, aber nur 4 Regeln aktiv; `label-has-associated-control`, `click-events-have-key-events`, `no-static-element-interactions` einschalten und die Treffer abarbeiten. | | `src/app/pages/dsr-page.tsx:402-405,446-486`, `eslint.config.mjs:87-90` |
| F6 | **Bundle.** Kein `React.lazy`, alle 19 Seiten statisch importiert; Recharts und MD-Editor im Initial-Bundle. Fünf Abhängigkeiten ohne einen Import (`react-dnd`, `react-dnd-html5-backend`, `react-slick`, `react-responsive-masonry`, `next-themes`); `motion` und `embla-carousel-react` nur über UI-Dateien, die selbst nirgends importiert werden. Rund 20 ungenutzte Dateien in `components/ui/` (u. a. `sidebar.tsx` mit 726 Zeilen, `carousel`, `navigation-menu`, `chart`, `calendar`, `command`, `drawer`, `form`, `menubar`, `resizable`, `pagination`). Lazy-Routen, Deps und tote Dateien entfernen, Bundle-Größe als CI-Artefakt. | | `src/app/routes.tsx:2-20`, `package.json`, `vite.config.ts` |
| F7 | **Große Seiten zerlegen**, nach dem Muster von `components/case-detail/` (Tab-Komponenten + Context): `playbook-detail-page.tsx` (779 Zeilen, 17 `useState`), `dsr-page.tsx` (650), `new-case-dialog.tsx` (554, Hook `useMultiStepForm` existiert bereits), `tom-page.tsx`/`avv-page.tsx` (544/509, gemeinsames Muster). | | – |
| F8 | `tsconfig`: `noUncheckedIndexedAccess` aktivieren, sobald F1/F2 durch sind. `package.json`: Name `@figma/my-make-file` und toten `pnpm.overrides`-Block korrigieren. `vite.config.ts`: Kommentar "required for Make" prüfen und entfernen. | | `tsconfig.json:18-23`, `package.json:2,95-99` |

### Phase 4 – Tests und Evals (laufend, parallel zu Phase 2–3)

| # | Maßnahme | Befund | Beleg |
| :--- | :--- | :--- | :--- |
| T1 | **Ungetestete Module zuerst.** Services ohne eine einzige Testreferenz (1 114 Zeilen): `annotated_document_service`, `data_breach_service`, `connection_checks`, `finding_chat_service`, `prompt_template_service`, `org_profile_loader`, `dsr_response_service`, `departments_loader`. Route-Module ohne Tests: `mitigations` (9 Routen), `exports`, `admin_prompt_templates`, `legal_bases`, `case_templates`, `app_config`. Gemessene Coverage bestätigt das: `notification_service` 8 %, `annotated_document_service` 16 %, `run_checks_service` 22 %, `auth` 27 %, `cases/crud` 25 %. | | Coverage-Report, `backend/tests/` |
| T2 | **Test-Infrastruktur.** `_create_case` ist in 7 Dateien kopiert → Factory-Fixtures in `conftest.py`. Keine Transaktions-Isolation (Session-Scope-Seed, Testdaten bleiben liegen) → function-scoped Rollback. `limiter.enabled=False` global → ein Test, der 429 erzwingt. Einheitlicher `requires_db`-Marker statt Docstring-Hinweisen. | | `backend/tests/conftest.py:22-75` |
| T3 | **Frontend-Coverage messbar machen.** `@vitest/coverage-v8` installieren, `coverage`-Block in `vite.config.ts`, Gate auf gemessenem Stand. `msw` ist installiert, wird aber nicht genutzt (stattdessen 15× `vi.mock` auf API-Module → Mapper in `lib/api/*` bleiben ungetestet). Tests für `playbook-detail-page`, `tom-page`, `useMultiStepForm`, `AuthContext`, `CaseDetailContext`. | | `vite.config.ts:8-12`, `src/app/pages/case-detail-page.test.tsx` |
| T4 | **E2E ehrlich machen.** 7 Assertions in `checks.spec.ts`/`document-upload.spec.ts` stehen hinter `if (isVisible)` mit `.catch(() => false)`; der Kommentar sagt selbst "Test passes regardless". `data-testid` an Fall-Karten/Tabs, harte Assertions, `@smoke`-Set von 2 auf ~6 erweitern, `retries` von 2 auf 1, restliche Specs nightly. | | `e2e/checks.spec.ts:34-81`, `e2e/document-upload.spec.ts:42-73`, `playwright.config.ts:19` |
| T5 | **Nightly-Eval mit LLM.** In CI laufen nur Offline-Evals; `CheckVerdictAccuracy`, `CheckSeverityCloseness`, `CheckConfidenceCalibration` und OCR werden nie ausgeführt. Die Kernqualität des Produkts (Check-Verdikt) ist damit ungemessen. Nightly-Job mit `--llm --ocr` gegen Ollama, `--strict`, JSON-Ergebnis als Artefakt trenden. Anschluss an das bestehende [Verbesserungskonzept Analysequalität](analysequalitaet-verbesserungen.md). | | `backend/evals/run.py:88-106`, `test.yml:70-71` |
| T6 | Migrations-Roundtrip in CI (`upgrade head` → `downgrade -1` → `upgrade head`). Heute wird das Test-Schema per `create_all` erzeugt, kein Test führt eine Migration aus. | | `conftest.py:57` |

### Phase 5 – Betrieb und Dokumentation (2 Wochen)

| # | Maßnahme | Befund | Beleg |
| :--- | :--- | :--- | :--- |
| O1 | **Reproduzierbare Builds.** Nur 5 von 38 Python-Paketen exakt gepinnt, Rest `>=` ohne Obergrenze trotz Kommentar "pinned for reproducibility" → `requirements.in` + `pip-compile` mit Hashes. `Dockerfile.frontend` nutzt `npm install` ohne Lockfile → `COPY package-lock.json` + `npm ci`. | CI-grün ≠ Image-grün. | `backend/requirements.txt`, `Dockerfile.frontend:10-11` |
| O2 | Backend-Dockerfile: `build-essential` wird in einem separaten Layer entfernt (Image schrumpft nicht) → Multi-Stage. Nginx als `nginx-unprivileged`. | | `backend/Dockerfile:10-24`, `Dockerfile.frontend:28-31` |
| O3 | Compose: Backend `depends_on` um MinIO und Weaviate (`service_healthy`) ergänzen; Frontend-Healthcheck und `restart`-Policy (CI umgeht das heute mit einer curl-Schleife). | | `docker-compose.yml:100-104,141-148`, `test.yml:112-122` |
| O4 | **Backup/Restore.** Kein Backup-Service, kein Runbook, RTO/RPO undefiniert (die eigene System-Inspection bewertet das mit 4/10). `pg_dump`-Sidecar + MinIO-Mirror + dokumentiertes Restore, einmal geprobt. | | `docker-compose.yml:150-155`, `system-inspection.md:153,161` |
| O5 | Advisory-Lock um `alembic upgrade` im Entrypoint (mehrere Replicas migrieren sonst parallel). | | `backend/entrypoint.sh:4-7` |
| O6 | **Doku bereinigen.** `system-inspection.md` behauptet 85 % Coverage, "keine Playwright-Tests", FastAPI 0.104 – alles falsch gegenüber Code. `next_steps.md`/`requirements_gap.md` referenzieren `api/routes/cases.py` und `005_add_user_role.sql`, die nicht mehr existieren, und widersprechen sich beim Retention-Status. Entweder als "historisch, Feb 2026" markieren oder neu erheben. | | `system-inspection.md:207-219,330-359`, `next_steps.md:12,32`, `requirements_gap.md:73-80` |
| O7 | ADR-Verzeichnis (`projekt/adr/`, MADR-Format) für die tragenden Entscheidungen: Alembic als einzige Schemaquelle, Weaviate/Celery optional, LLM-Provider-Abstraktion, kein Mandanten-Scoping (siehe Abschnitt 4). | | – |

---

## 4. Strategische Entscheidungen (nicht im Plan enthalten, brauchen Klärung)

Diese Punkte sind größer als ein PR und verändern das Produkt. Sie gehören in den Plan
erst, wenn die Richtung entschieden ist.

**4.1 Mandanten- und Fachbereichstrennung.** Es gibt kein `org_id`/`tenant`-Feld im
Datenmodell. Autorisierung ist rein rollenbasiert und global: jeder `viewer` liest alle
Vorgänge, Dokumentinhalte, DSFA, Datenpannen und DSR-Anfragen aller Fachbereiche,
inklusive besonderer Kategorien (`documents.py:244-304`, `crud.py:393`,
`findings.py:427` nennt das explizit "org-wide"). Solange das Tool von *einem* DSB-Team
für *eine* Organisation betrieben wird, ist das vertretbar. Sobald Fachbereiche selbst
Zugang bekommen oder mehrere Organisationen eine Instanz teilen, ist es ein IDOR-Problem
quer durch alle Routen. Die Nachrüstung ist ein eigenes Projekt (Modell, Migration,
zentraler Query-Helper, alle Routen, Tests).

**Entscheidung (2026-09-05): Single-Org.** Eine Instanz bedient genau eine
Organisation, betrieben von deren DSB-Team. Konsequenzen:

- Kein Org-/Tenant-Scoping im Datenmodell; RBAC (`viewer`/`editor`/`admin`) bleibt die
  einzige Autorisierungsebene. Das ist bewusst akzeptiert und wird als ADR festgehalten
  (Phase 5, O7).
- Wer eine Instanz mehreren Organisationen zugänglich macht, verstößt gegen das
  Betriebsmodell; die Doku (Administration) muss das ausdrücklich sagen.
- Die Sicherheitsmaßnahmen der Phase 1 (S1–S10) bleiben unverändert nötig; sie sind
  unabhängig von der Mandantenfrage.
- Falls Fachbereiche später eigenen Zugang bekommen sollen, ist das ein neues Projekt
  mit eigener Analyse, nicht eine Erweiterung dieses Plans.

**4.2 Löschkonzept.** Retention archiviert nur (`case.archived_at = now`), löscht aber
weder Dokumente, Storage-Blobs, Weaviate-Chunks, Findings noch LLM-Cache
(`retention_service.py:80-99`). Es gibt kein `DELETE /admin/users/{id}` und keinen
Nutzer-Datenexport. Für ein DSGVO-Werkzeug, das Art.-17-Prozesse *prüft*, sollte die
eigene Löschung vollständig sein. **Entscheidung nötig: Hard-Delete nach Frist
(mit welcher Frist) oder bewusst nur Archivierung?**

**4.3 Verschlüsselung at rest.** Fernet wird nur für Webhook-Secrets genutzt. Dokumente,
Volltexte, Findings liegen unverschlüsselt in Postgres/MinIO (`storage.py:96-114` ohne
SSE-Header). Ob Anwendungs-, Storage- (MinIO SSE) oder Volume-Verschlüsselung, ist eine
Betriebsentscheidung; mindestens dokumentiert werden muss sie.

**4.4 Default-User ohne OIDC.** Bei `oidc_enabled=false` ist jede Anfrage der feste
Default-User mit `RBAC_DEFAULT_ROLE` (`main.py:119-140`, `core/auth.py:271-286`). In
Produktion wird OIDC erzwungen, aber `development` mit öffentlich erreichbarem Port ist
offen. Option: Bind an Loopback erzwingen oder Pre-Shared-Token.

---

## 5. Zielwerte und Messung

| Metrik | Ist (Analyse) | Nach Phase 0 (gemessen) | Ziel nach Phase 4 | Messung |
| :--- | :--- | :--- | :--- | :--- |
| `tsc --noEmit` Fehler | 81 | **0, CI-Gate** | 0 | CI |
| ESLint Errors / Warnings | 8 / 36 | **0 / 0, CI-Gate** | 0 / 0 | CI |
| Backend-Coverage | 58 % | **59,9 %, Gate 58 %** | Gate ≥ 70 % (Ratchet) | `pytest --cov` |
| Frontend-Coverage | nicht messbar | nicht messbar (T3) | Gate ≥ 60 % | `vitest --coverage` |
| Route-Module ohne Test | 6 | 6 | 0 | Skript in CI |
| Services ohne Test | 8 | 8 | 0 | Skript in CI |
| E2E in CI (harte Assertions) | 2 | 2 | ≥ 6 smoke, Rest nightly | Playwright-Report |
| Ruff C901 > 15 | 4 (nicht geprüft) | **4 (per-file-ignore), Gate aktiv** | 0 | CI |
| mypy-Fehler | nicht geprüft | nicht geprüft (R5) | 0 in `core/`, `services/` | CI |
| Security-Scanner gatend | 4 von 6 | **6 von 6** | 6 von 6 | CI |
| Migrations-Drift-Check | keiner | **aktiv, 1 Drift behoben** | aktiv | CI |
| LLM-Eval-Trend | nicht gemessen | – | nightly, Artefakt | Nightly-Job |
| Verifizierte Bugs | 8 offen (B1–B8) | **0 offen (B1–B9)** | 0 | Regressionstests |

Die Zielwerte 85 % FE / 90 % BE aus `system-inspection.md` werden bewusst **nicht**
übernommen: Bei ~11 000 Backend-Statements liegen die letzten 20 % in Infrastruktur-Glue
(Celery, Weaviate, SMTP, OCR), dessen Tests teurer sind als ihr Nutzen. 70 % mit
vollständiger Abdeckung der Routen und Domänenlogik ist das bessere Ziel.

---

## 6. Was bewusst nicht empfohlen wird

- **Kein i18n-Framework jetzt.** Die deutschen Strings sind hartkodiert und die Label-Maps
  fünffach dupliziert. Die Duplikate gehören zusammengeführt (F2), aber ein i18n-System
  ohne konkrete Zweitsprache-Anforderung ist Aufwand ohne Ertrag.
- **Kein Big-Bang auf TanStack Query.** F4 migriert seitenweise, beginnend mit den vier
  strukturgleichen Katalogseiten. Wer alle 20 Seiten in einem PR umstellt, bekommt einen
  nicht reviewbaren Diff.
- **Keine Aufteilung von `config.py`** (653 Zeilen, ~120 Felder) vor R5. Ohne Typchecker
  ist ein Umbau der Settings-Klasse riskanter als ihr Zustand.
- **Kein Mutation-Testing, kein Load-Testing** in diesem Plan. Beides steht in
  `system-inspection.md`, ist aber erst sinnvoll, wenn die Gates aus Phase 0 stehen.

---

## 7. Reihenfolge und Aufwand

| Phase | Dauer | Parallelisierbar | Ergebnis |
| :--- | :--- | :--- | :--- |
| 0 – Bugs + Gates | 1 Woche (**erledigt**) | B1–B9 und G1–G7 unabhängig | 9 Bugs weg, 7 Gates aktiv, Frontend erstmals typsicher in CI |
| 1 – Security/DSGVO | 2–3 Wochen | S1–S3 sofort, S4–S10 je ein PR | Rate-Limit wirksam, Upload gehärtet, Audit-Log belastbar |
| 2 – Backend-Robustheit | 3–4 Wochen | R1–R4 zuerst, R5 parallel | Keine Loop-Blockaden, Celery-Fehler sichtbar, LLM-Kosten begrenzt, Typchecker aktiv |
| 3 – Frontend | 3–4 Wochen | F1–F2 zuerst (Voraussetzung für G1), dann F3–F8 | Mock-Daten weg, Fehler sichtbar, a11y-Basis, Bundle kleiner |
| 4 – Tests/Evals | laufend | T1 pro Modul, T5 eigener Job | Ratchet auf 70 %, E2E ehrlich, LLM-Qualität gemessen |
| 5 – Betrieb/Doku | 2 Wochen | O1–O7 unabhängig | Reproduzierbare Builds, Backup-Runbook, Doku konsistent |

Phasen 1 und 3 können parallel laufen (Backend vs. Frontend). Phase 4 läuft als
Begleitung: jede Maßnahme aus Phase 1–3 bringt ihren Test mit.
