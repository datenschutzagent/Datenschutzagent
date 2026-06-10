# Dokumente

Pro Vorgang können beliebig viele Dokumente hochgeladen werden. Unterstützte Formate: **DOCX**, **PDF**, **XLSX**, **PPTX**, **CSV**, **DOC** sowie gescannte Bilder (**JPG**, **PNG**, **TIFF**, via OCR). Der Text wird automatisch extrahiert und für Playbook-Checks sowie VVT-Normalisierung genutzt.

## Upload

- **Einzelupload:** In der Vorgangsdetailseite im Tab „Dokumente“ eine Datei und einen Dokumenttyp (z. B. VVT, Einwilligung) wählen.
- **Mehrfach-Upload:** Mehrere Dateien desselben Typs in einem Schritt hochladen (Bulk-Upload). Alle erhalten denselben Dokumenttyp; die Version wird pro Typ automatisch fortlaufend vergeben (v1, v2, …).

Beim Hochladen wird die Datei im konfigurierten Storage (lokal oder MinIO) abgelegt und in der Datenbank erfasst. Die **Textextraktion** läuft – bei aktiviertem Celery/Redis – asynchron; der Upload antwortet sofort mit 201. Bis die Extraktion fertig ist, kann der Inhalt noch leer sein.

Der extrahierte Text erhält **Fundstellen-Marker**: Mehrseitige PDFs tragen pro Seite einen Anker `[Seite N]`, mehrseitige PPTX-Präsentationen pro Folie einen Anker `[Folie N]` (inkl. Sprechernotizen unter `--- Notizen ---`), XLSX-Tabellen und CSV-Dateien eine führende Spalte „Zeile“ mit der 1-basierten Zeilennummer (zusätzlich zu den Spaltenbuchstaben A, B, C, …). LLM-Belege wie „Seite 3“, „Folie 2“ oder „Sheet X, Spalte C, Zeile 12“ sind dadurch direkt im Dokument nachprüfbar. Bekannte Grenze: Text in PPTX-Diagrammen und SmartArt wird nicht extrahiert.

## Versionierung

Pro Vorgang und Dokumenttyp gibt es Versionsnummern (v1, v2, …). Wenn Sie erneut ein Dokument vom gleichen Typ hochladen, entsteht die nächste Version. Das Frontend zeigt die Version (z. B. „VVT v2“) und beim Upload einen Hinweis, dass eine neue Version angelegt wird.

## OCR (gescannte PDFs)

PDFs mit wenig oder keinem extrahierbaren Text (z. B. eingescannte Seiten) werden bei aktivierter OCR-Funktion automatisch per **Ollama Vision** verarbeitet. Dokumente, deren Text per OCR gewonnen wurde, sind im Frontend mit dem Badge **„Text per OCR extrahiert“** gekennzeichnet.

## Inhalt anzeigen und Kommentare

- **Inhalt:** Der extrahierte Text kann im Dokumenten-Tab bzw. in einer Dokumentenansicht gelesen werden.
- **Kommentare:** Pro Dokument können Kommentare hinzugefügt werden (Rolle editor/admin). Sie erscheinen sortiert nach Erstellungszeit.

## Dokument löschen

Einzelne Dokumente können gelöscht werden (Rolle editor/admin). Dabei werden Eintrag in der Datenbank und Datei im Storage entfernt; bei aktivierter Weaviate-Indexierung werden die zugehörigen Chunks gelöscht.
