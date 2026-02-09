# DSB-Report

Der **DSB Summary Report** fasst den Vorgang aus Sicht des Datenschutzbeauftragten zusammen: Anzahl Dokumente, Findings (inkl. kritisch/hoch), Hinweise zu DSFA, VVT-Vollständigkeit, Risiken, Empfehlungen und nächste Schritte.

## Abruf

- **Im Frontend:** In der Vorgangsdetailseite der Button **„DSB-Report“** startet den Download des Reports als **Markdown**-Datei.
- **API:** `GET /api/v1/cases/{id}/dsb-report` – Query `format=markdown` (Standard, Download mit Content-Disposition) oder `format=json` für die strukturierte JSON-Antwort (case_id, case_title, generated_at, status, summary, risks, recommendations, open_questions, next_steps).

## Inhalt (Überblick)

- **Summary:** total_documents, total_findings, critical_findings, high_findings, dsfa_required, vvt_completeness.
- **Risiken, Empfehlungen, offene Fragen, nächste Schritte** – vom Backend-Service aus den Findings und VVT-Daten erzeugt.
