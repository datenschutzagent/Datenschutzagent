# Analysequalität – Bestandsaufnahme & Verbesserungskonzept

**Stand:** Juli 2026
**Gegenstand:** Dokumentverarbeitung, Playbook-Checks und nachgelagerte Analysen (Findings, DSB-Report, VVT/DSFA/AVV)
**Ziel:** Konkrete, priorisierte Maßnahmen für qualitativ bessere Analyseergebnisse — betrachtet aus fünf Perspektiven.

---

## 1. Ist-Zustand: Wie das System heute arbeitet

### 1.1 Dokumenten-Pipeline

```
Upload → Storage (local/MinIO) → Extraktion (Celery) → DocumentModel.content
      → optional Weaviate-Indexierung → Playbook-Checks (full_text / rag)
```

- **Upload** (`backend/app/api/routes/documents.py`): 10 Formate (PDF, DOCX, XLSX, PPTX, CSV, DOC, Bilder), Magic-Byte-Validierung, 50 MB Limit, Versionierung pro Dokumenttyp.
- **Extraktion** (`backend/app/services/document_processor.py`, `pdf_extractor.py`):
  PDFs über PyMuPDF mit layout-erhaltendem Markdown (`pymupdf4llm`), Seiten-Anker `[Seite N]`;
  Office-Formate mit Tabellen→Markdown, Kopf-/Fußzeilen, Fußnoten, Speaker-Notes.
- **OCR** (`backend/app/services/ocr_service.py`): ausschließlich Vision-LLM (`qwen2.5-vl` via
  Ollama/OpenAI-kompatibel), per-Page-Erkennung dünner Seiten, DPI-Eskalation bei Retry,
  Cap bei 200 Seiten. Qualitätssignale (`extraction_char_count`, `extraction_ocr_ratio`,
  `extraction_ocr_low_quality_pages`) werden am Dokument persistiert.
- **RAG** (`backend/app/services/weaviate_service.py`): strukturbewusstes Chunking
  (Tabellen-Header werden je Chunk wiederholt), hybrides Retrieval (BM25 + Vektor).
  **Indexierung ist per Default deaktiviert** (`weaviate_indexing_enabled=False`).

### 1.2 Playbook-Engine

- 30 YAML-Playbooks (`backend/app/data/playbooks/`); jeder Check ist eine
  **natürlichsprachliche Prompt-Instruktion** — die gesamte Prüf­logik ist an das LLM
  delegiert (einzige regelbasierte Komponente: DSFA-Screening über `risk_config.yaml`).
- Ausführung: `run_checks_service.py` → `check_runner.py`; parallel mit Semaphore
  (`max_concurrent_llm_calls=2`), Timeout pro Check, Dedup über `(check_name, document_id)`.
- **Kontext-Handling:**
    - 15.000 Zeichen pro Dokument (`max_context_chars_per_doc`); längere Dokumente laufen
      per **Map-Reduce über max. 6 Fragmente** — Inhalt jenseits ~90k Zeichen wird
      **stillschweigend verworfen**.
    - **Cross-Dokument-Checks trunkieren hart** statt Map-Reduce
      (`run_cross_document_check`) — ausgerechnet Vergleichs-Checks verlieren Inhalt.
    - RAG-Kontext wird nach dem Join **hart auf Zeichenlänge geschnitten**
      (`[... truncated ...]`), nicht satzbewusst.
    - Ist Weaviate nicht erreichbar, **fällt RAG still auf Volltext zurück** (nur Log-Eintrag).

### 1.3 Bereits vorhandene Qualitäts-Guardrails

Positiv: Das System hat mehr Schutzmechanismen als auf den ersten Blick sichtbar.

| Guardrail | Ort | Wirkung |
|---|---|---|
| Evidence-Grounding | `core/grounding.py` | Halluzinierte Zitate werden verworfen, Confidence gesenkt |
| Output-Validator + `ModelRetry` | `check_runner.py` | Selbstkorrektur bei inkonsistentem Schema / 0 % Grounding |
| Severity-Rubrik | `CHECK_OUTPUT_GUIDANCE` | Einheitliche Schweregrad-Definitionen im Prompt |
| Self-Consistency-Voting | `_aggregate_self_consistency` | Implementiert, aber **per Default aus** (N=1) |
| LLM-Cache | `core/llm_cache.py` | Invalidiert automatisch bei Playbook-/Modell-Änderung |
| Circuit-Breaker + Retries | `core/llm.py` | Resilienz gegen Provider-Ausfälle |
| Prompt-Injection-Härtung | `core/prompt_security.py` | Marker-Wrapping von Dokumenttext |
| Eval-Gate | `backend/evals/` | CI-Gate: Extraktion, Grounding-F1, 4 LLM-Gold-Fälle |

### 1.4 Die zentralen Qualitätslücken

1. **Confidence wird berechnet, aber nie auf Findings gespeichert oder angezeigt** —
   `add_finding` verwirft den Wert; Reviewer können nicht nach Belastbarkeit triagieren.
2. **Evidenz ist nur Zitat-Text** — keine klickbare Fundstelle, obwohl Seiten-Anker im
   Extrakt existieren und der Grounding-Match die Position bereits kennt.
3. **Kein Lern-Loop** — Finding-Overrides und Kommentare fließen weder in Prompts noch
   in die Eval-Suite (nur 4 Gold-Fälle) zurück.
4. **Stille Degradierung** — Bilder ohne OCR landen als `DONE` mit leerem Inhalt;
   Truncation/Map-Reduce-Verlust und RAG-Fallback sind für Nutzer unsichtbar.
5. **Binäres Verdict** — fehlende Information wird als Verstoß gewertet, nicht als
   „nicht prüfbar“; das erzeugt vermeidbare False-Positives.

---

## 2. Verbesserungsvorschläge nach Perspektiven

### Perspektive A — Datenschutzbeauftragte:r (fachlich-juristische Qualität)

| # | Vorschlag | Begründung / Ansatzpunkt |
|---|---|---|
| A1 | **Drittes Verdict „nicht prüfbar“** statt binär compliant/non-compliant | `CheckResult` (`check_runner.py`) kennt nur `is_compliant`. Fehlende Information ≠ Verstoß. Enum `compliant / non_compliant / not_assessable` + eigener Finding-Typ „Informationslücke“ senkt False-Positives massiv. |
| A2 | **Klickbare Fundstellen** (Seite/Offset) statt reiner Zitat-Strings | Seiten-Anker `[Seite N]`/`[Folie N]` existieren bereits im Extrakt; der Grounding-Match liefert die Position. Offset + Seite am Evidence-Objekt speichern, UI-Highlight im Dokument. Der DSB-Report verspricht bereits „konkrete Fundstellen“ (`dsb-report-view.tsx`) — einlösen. |
| A3 | **Rechtsgrundlagen-Referenz pro Check strukturieren** | Checks um `legal_refs: [Art. 30 Abs. 1 lit. c]` erweitern; im Finding ausweisen. Erhöht Nachvollziehbarkeit und Prüfbarkeit durch Aufsichtsbehörden. |
| A4 | **`mandatory`-Flag durchsetzen** | Wird heute nirgends ausgewertet. Mandatory-Checks: Self-Consistency erzwingen, im Report separat ausweisen, Fall nicht „grün“ solange mandatory offen. |
| A5 | **DSB-Report: LLM-Executive-Summary + kontextuelle next_steps** | `next_steps` ist eine hartcodierte 3-Punkte-Liste (`dsb_report_service.py`). Eine LLM-Synthese über die konkreten Findings (mit dem `analysis=True`-Modell) liefert deutlich brauchbarere Berichte. |

### Perspektive B — LLM-/ML-Engineering (Modell- & Prompt-Qualität)

| # | Vorschlag | Begründung / Ansatzpunkt |
|---|---|---|
| B1 | **Confidence auf Findings persistieren & anzeigen** | Wird berechnet (Grounding, Truncation ×0.9), aber in `add_finding` verworfen. `ConfidenceBadge`-Komponente existiert bereits (nur DSFA/AVV). Ohne sichtbare Confidence kann der DSB nicht triagieren. |
| B2 | **Selektive Self-Consistency** | N=3 nur für mandatory-Checks bzw. Findings mit Severity ≥ high (zweiter Bestätigungslauf vor Persistierung). Kostenkontrolliert statt global. Code existiert (`_aggregate_self_consistency`). |
| B3 | **Cross-Doc-Checks auf Map-Reduce umstellen** | Aktuell harte Truncation pro Dokument (`run_cross_document_check`) — gerade Vergleichs-Checks (z. B. VVT vs. AVV) verlieren Inhalt. Vorhandene `build_context_windows` wiederverwenden. |
| B4 | **Map-Reduce-Cap dynamisch + Coverage-Warnung** | `long_doc_max_chunks=6` verwirft Inhalt > ~90k Zeichen stillschweigend. Mindestens: Coverage-Ratio berechnen und im Finding/Aktivitätslog ausweisen; besser: Cap nach Dokumentgröße skalieren. |
| B5 | **RAG-Qualität heben** | (a) Indexierung default aktivieren, sobald Weaviate läuft; (b) Retrieval-Query aus Check-Instruktion + Kategorie; (c) sentence-aware Truncation statt Hard-Cut (`check_runner.py`); (d) optionales Reranking. Voraussetzung: B7 (Evals) als Messlatte. |
| B6 | **Echten Tokenizer statt 3,5-Zeichen-Heuristik** | `core/tokens.py` schätzt grob; llama.cpp-Silent-Truncation ist die dokumentierte Gefahr. `tiktoken`/HF-Tokenizer je Provider → präzisere Budgets, weniger unbemerkter Kontextverlust. |
| B7 | **Eval-Suite ausbauen — wichtigster Hebel** | Heute 4 Gold-Fälle (`evals/llm_eval.py`). Ausbauen auf: Gold-Fälle pro Playbook-Kategorie, echte anonymisierte Dokumente, RAG-vs-full_text-Vergleich, Prompt-Regressionstests. Ohne Messlatte ist jede Prompt-/Modelländerung Blindflug. |
| B8 | **Fragment-Aggregation verfeinern** | `_aggregate_check_results`: „any violation wins + min confidence“ ist konservativ; fragment­übergreifende Widersprüche gehen verloren. Reduce-Schritt als LLM-Synthese über die Fragment-Ergebnisse. |

### Perspektive C — Dokument-/Datenqualität (Garbage in, garbage out)

| # | Vorschlag | Begründung / Ansatzpunkt |
|---|---|---|
| C1 | **Leere/dünne Extraktion sichtbar machen** | Bild-Upload ohne OCR → `DONE` mit leerem Content (`pdf_extractor.py`); Checks laufen dann auf nichts. Neuer Status `DONE_WITH_WARNINGS` bzw. UI-Banner bei `char_count < Schwellwert` oder hoher `ocr_low_quality_pages`. |
| C2 | **Autoretry für Extraktions-Task** | `extract_document_text` hat kein `autoretry` (Beat-Tasks schon); transienter Fehler = dauerhaft FAILED bis zum manuellen Re-Trigger. Retry + „Erneut extrahieren“-Button. |
| C3 | **Datei-Hash-Deduplizierung** | Kein Content-Hash beim Upload — Duplikate erzeugen doppelte Extraktion, Indexierung und doppelte Findings-Grundlage. SHA-256 bei Upload, Hinweis/Verknüpfung bei Treffer. |
| C4 | **Klassisches OCR-Fallback (Tesseract)** | OCR hängt zu 100 % am Vision-LLM. Tesseract als Fallback/Cross-Check (Konfidenz-Vergleich pro Seite) erhöht Robustheit, besonders on-prem ohne GPU. |
| C5 | **Spracherkennung durch Bibliothek ersetzen** | Stopwort-Heuristik DE/EN (`document_processor.py`) versagt bei kurzen/gemischten Texten. `lingua`/`fasttext` ist eine kleine, risikolose Verbesserung. |

### Perspektive D — Anwender:in / Human-in-the-Loop (Vertrauen & Lern-Loop)

| # | Vorschlag | Begründung / Ansatzpunkt |
|---|---|---|
| D1 | **Evidenz-Highlight im Dokument** (UI-Seite von A2) | Klick auf Zitat öffnet die Dokumentansicht an der Fundstelle. Größter Vertrauens-Hebel für Reviewer. |
| D2 | **False-Positive-Label + Begründungspflicht bei Override** | „Overruled“ vermengt „fachlich anders bewertet“ und „Modellfehler“. Getrenntes Label + Pflichtkommentar erzeugt Trainings-/Eval-Daten quasi gratis. |
| D3 | **Feedback-Loop schließen** | Overrules mit Begründung → (a) als Gold-Negativ-Fälle in die Eval-Suite, (b) optional als Few-Shot-Beispiele in den Check-Prompt (pro Playbook-Kategorie), (c) Override-Rate pro Check als Qualitätsmetrik → schwache Checks identifizieren und Instruktionen nachschärfen. |
| D4 | **Re-Run einzelner Checks/Findings** | Heute nur kompletter Run. Nach Dokument-Korrektur oder Prompt-Anpassung einen Check gezielt neu laufen lassen (Dedup-Set berücksichtigt das bereits per `(check_name, document_id)`). |
| D5 | **Degraded-Mode sichtbar machen** | RAG→full_text-Fallback und Truncation werden nur geloggt. Badge am Run/Finding („Analyse mit reduziertem Kontext“), damit Nutzer die Belastbarkeit einschätzen können. |

### Perspektive E — Betrieb / Kosten / Auditierbarkeit

| # | Vorschlag | Begründung / Ansatzpunkt |
|---|---|---|
| E1 | **Kosten-Tracking** | Token-Counter existieren (Prometheus), werden aber nie in € umgerechnet; keine per-Case/per-Run-API. Preis-Config je Modell + Kosten am Run-Objekt speichern. |
| E2 | **Qualitätsmetriken exportieren** | `grounding_ratio()` wird berechnet, aber nicht als Metrik exportiert; Acceptance-/Override-Rate fehlt. Prometheus-Gauges + kleines Qualitäts-Dashboard (auch als Verkaufsargument: „x % der Findings mit verifizierten Zitaten“). |
| E3 | **Run-Manifest für Reproduzierbarkeit** | Pro Check-Run persistieren: Modell + Version, Prompt-Template-Hash, Playbook-Revision, Strategie, Truncation/Coverage. Für DSGVO-Audits („Wie kam dieses Finding zustande?“) essenziell; der Cache-Key enthält die Bausteine bereits. |

---

## 3. Priorisierung

### Stufe 1 — Quick Wins (hoher Qualitätseffekt, geringes Risiko)

1. **B1** Confidence persistieren + anzeigen (Spalte + vorhandenes `ConfidenceBadge`)
2. **C1** Leere/dünne Extraktion als Warnung (statt stilles `DONE`)
3. **D5** Degraded-Mode/Truncation-Transparenz am Finding
4. **C2** Extraktions-Autoretry
5. **A5** Hardcodierte `next_steps` durch LLM-Synthese ersetzen

### Stufe 2 — strukturelle Qualitätshebel

6. **A1** Drittes Verdict „nicht prüfbar“ (Schema + Prompts + UI)
7. **B7/D3** Eval-Ausbau + Override-Feedback als Gold-Daten (der Lern-Loop)
8. **A2/D1** Fundstellen-Anker + Evidenz-Highlight
9. **B3** Cross-Doc Map-Reduce; **B2** selektive Self-Consistency für mandatory/high

### Stufe 3 — Ausbau

10. **B5** RAG-Aktivierung + Retrieval-Tuning (erst nach Eval-Messlatte),
    **C4** Tesseract-Fallback, **E1–E3** Kosten/Metriken/Run-Manifest,
    **C3** Hash-Dedup, **B6** echter Tokenizer.

> **Leitprinzip:** Erst **messen** (Evals), dann **sichtbar machen**
> (Confidence, Coverage, Fundstellen), dann **optimieren**
> (RAG, Self-Consistency, Prompts).
