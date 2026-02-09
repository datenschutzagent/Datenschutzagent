# VVT-Normalisierung

Die **VVT-Normalisierung** (Verarbeitungsverzeichnis) extrahiert aus dem ersten VVT-Dokument (oder einem gewählten Dokument) des Vorgangs strukturierte Felder und erkennt das verwendete Template. Die Ausgabe kann im Case-Detail im **Tab „VVT“** eingesehen werden.

## Anzeige

- Im Vorgang den Tab **„VVT-Normalisierung“** öffnen. Die Ansicht lädt die Daten von `GET /api/v1/cases/{id}/vvt-normalization` (optional mit `document_id` für ein bestimmtes VVT-Dokument).
- Angezeigt werden u. a. erkanntes Template (`source_template`), kanonische Felder mit Status, Wert und ggf. Evidence/Findings.

## Export

- **CSV:** Über die API `GET /api/v1/cases/{id}/vvt-normalization/export` (Standardformat CSV). Im Frontend ggf. über einen Export-Button.
- **DOCX (Ziel-Template):** Gleicher Endpoint mit `?format=docx` – liefert ein DOCX mit Dokumentname, erkanntem Template und Tabelle der normalisierten Felder.

Die Case-Sprache (`language`) fließt in die LLM-Prompts ein, sodass Feldwerte und Texte sprachangepasst sein können (DE/EN).
