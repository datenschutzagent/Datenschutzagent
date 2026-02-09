# Annotierte Dokumente

Zu Dokumenten mit Findings können **annotierte Versionen** erzeugt werden: Das Originaldokument wird mit den zugehörigen Findings (z. B. als Kommentare oder Markierungen) angereichert und als DOCX oder PDF zum Download angeboten.

## Liste und Download

- **Tab „Annotierte Dokumente“** in der Vorgangsdetailseite: Zeigt die Liste der Dokumente, für die annotierte Versionen verfügbar sind (mit Anzahl der Findings pro Dokument).
- **Download:** Pro Dokument können Sie die annotierte Version als **DOCX** (Standard) oder **PDF** herunterladen. Die API: `GET /api/v1/cases/{id}/annotated-documents/{document_id}` (DOCX) bzw. `?format=pdf` für PDF.

Der Button **„Kommentierte Dokumente“** im Case-Header wechselt in der Regel in den Tab „Annotierte Dokumente“, von wo aus die Downloads gestartet werden.
