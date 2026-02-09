# Dokumente

Pro Vorgang können beliebig viele Dokumente hochgeladen werden. Unterstützte Formate: **DOCX**, **PDF**, **XLSX**. Der Text wird automatisch extrahiert und für Playbook-Checks sowie VVT-Normalisierung genutzt.

## Upload

- **Einzelupload:** In der Vorgangsdetailseite im Tab „Dokumente“ eine Datei und einen Dokumenttyp (z. B. VVT, Einwilligung) wählen.
- **Mehrfach-Upload:** Mehrere Dateien desselben Typs in einem Schritt hochladen (Bulk-Upload). Alle erhalten denselben Dokumenttyp; die Version wird pro Typ automatisch fortlaufend vergeben (v1, v2, …).

Beim Hochladen wird die Datei im konfigurierten Storage (lokal oder MinIO) abgelegt und in der Datenbank erfasst. Die **Textextraktion** läuft – bei aktiviertem Celery/Redis – asynchron; der Upload antwortet sofort mit 201. Bis die Extraktion fertig ist, kann der Inhalt noch leer sein.

## Versionierung

Pro Vorgang und Dokumenttyp gibt es Versionsnummern (v1, v2, …). Wenn Sie erneut ein Dokument vom gleichen Typ hochladen, entsteht die nächste Version. Das Frontend zeigt die Version (z. B. „VVT v2“) und beim Upload einen Hinweis, dass eine neue Version angelegt wird.

## OCR (gescannte PDFs)

PDFs mit wenig oder keinem extrahierbaren Text (z. B. eingescannte Seiten) werden bei aktivierter OCR-Funktion automatisch per **Ollama Vision** verarbeitet. Dokumente, deren Text per OCR gewonnen wurde, sind im Frontend mit dem Badge **„Text per OCR extrahiert“** gekennzeichnet.

## Inhalt anzeigen und Kommentare

- **Inhalt:** Der extrahierte Text kann im Dokumenten-Tab bzw. in einer Dokumentenansicht gelesen werden.
- **Kommentare:** Pro Dokument können Kommentare hinzugefügt werden (Rolle editor/admin). Sie erscheinen sortiert nach Erstellungszeit.

## Dokument löschen

Einzelne Dokumente können gelöscht werden (Rolle editor/admin). Dabei werden Eintrag in der Datenbank und Datei im Storage entfernt; bei aktivierter Weaviate-Indexierung werden die zugehörigen Chunks gelöscht.
