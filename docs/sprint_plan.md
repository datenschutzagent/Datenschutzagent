# Sprint-Plan (aktuell)

Stand: Nach Roadmap-/Gap-Abgleich. Dokumentation ist mit Code abgeglichen; dieser Sprint fokussiert auf **kommentierte Dokumente (Artefakte)**.

---

## Sprint-Ziele

1. **Dokumentation** – roadmap, requirements_gap, next_steps auf Code-Stand gebracht (DSB-Report ✅, VVT CSV-Export ✅).
2. **Backend: Annotierte Dokumente** – Service und API, die aus Case + Findings annotierte DOCX erzeugen (Kommentare/Footnotes zu Findings).
3. **Frontend: AnnotatedDocumentsView** – von Mock auf echte API umstellen (Liste generierter Artefakte, Download).

---

## Backlog

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Docs: requirements_gap.md, roadmap.md, next_steps.md abgleichen | ✅ |
| 2 | docs/sprint_plan.md anlegen | ✅ |
| 3 | Backend: Service „annotated document“ (Findings → DOCX mit Kommentaren) | ✅ |
| 4 | Backend: `GET /cases/{id}/annotated-documents` (Liste), `GET /cases/{id}/annotated-documents/{document_id}` (Download DOCX) | ✅ |
| 5 | Frontend: AnnotatedDocumentsView an API anbinden, Mock entfernen | ✅ |

---

## Folgesprint (optional)

- Mehrfach-Upload (mehrere Dateien pro Request).
- Audit-Log (Check-Läufe, Finding-Status protokollieren).
- Cross-Document-Checks (Multi-Dokument-Kontext im Check Runner).
