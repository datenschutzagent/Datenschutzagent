# VVT-Normalisierung

Die **VVT-Normalisierung** (Verarbeitungsverzeichnis) extrahiert aus dem ersten VVT-Dokument (oder einem gewählten Dokument) des Vorgangs strukturierte Felder und erkennt das verwendete Template. Die Ausgabe kann im Case-Detail im **Tab „VVT“** eingesehen werden.

## Anzeige

- Im Vorgang den Tab **„VVT-Normalisierung“** öffnen. Die Ansicht lädt die Daten von `GET /api/v1/cases/{id}/vvt-normalization` (optional mit `document_id` für ein bestimmtes VVT-Dokument).
- Angezeigt werden u. a. erkanntes Template (`source_template`), kanonische Felder mit Status, Wert und ggf. Evidence/Findings.

## Export

- **CSV:** Über die API `GET /api/v1/cases/{id}/vvt-normalization/export` (Standardformat CSV). Im Frontend ggf. über einen Export-Button.
- **DOCX (Ziel-Template):** Gleicher Endpoint mit `?format=docx` – liefert ein DOCX mit Dokumentname, erkanntem Template und Tabelle der normalisierten Felder.

Die Case-Sprache (`language`) fließt in die LLM-Prompts ein, sodass Feldwerte und Texte sprachangepasst sein können (DE/EN).

## Große Dokumente und Qualitätssicherung

- **Map-Reduce:** Überschreitet das Dokument das Kontextlimit (`MAX_CONTEXT_CHARS_VVT`, Standard 25.000 Zeichen), wird es in satzbewusste Fragmente zerlegt, fragmentweise extrahiert und feldweise zusammengeführt — Verarbeitungstätigkeiten jenseits des Limits gehen nicht mehr verloren. Beim Zusammenführen schlägt `filled` den Status `missing`; liefern zwei Fragmente widersprüchliche Werte für dasselbe Feld, wird das Feld als `inconsistent` markiert und das Finding nennt beide Werte. Konfiguration: `VVT_MAP_REDUCE_ENABLED` (Standard `true`), `VVT_MAX_CHUNKS` (Standard 8).
- **Wert-Verifikation (Grounding):** Extrahierte Feldwerte werden gegen den Dokumenttext geprüft (`EVIDENCE_GROUNDING_ENABLED`). Wirken alle Werte erfunden, fordert das System das Modell zur Selbstkorrektur auf; einzelne nicht verifizierbare Werte bleiben erhalten, erhalten aber den Prüfhinweis „Wert konnte nicht im Dokumenttext verifiziert werden“ im Finding.
