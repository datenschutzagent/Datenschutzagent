# Sprint-Plan (aktuell)

Stand: Nach Umsetzung Option A (Playbook-Detail, Docs, Mehrfach-Upload). Vorheriger Sprint (Annotated Documents) abgeschlossen.

---

## Sprint-Ziele (dieser Sprint – abgeschlossen)

1. **Playbook-Detail auf API** – `playbook-detail-page.tsx` nutzt `getPlaybook(playbookId)`; bei 404 „Playbook nicht gefunden“.
2. **Dokumentation** – roadmap.md, requirements_gap.md, next_steps.md: Playbook-Detail als API; Activity-Timeline als Mock bis Audit-Log.
3. **Mehrfach-Upload** – Backend: `POST /api/v1/documents/bulk`; Frontend: Upload-Zone nutzt Bulk bei mehreren Dateien gleichen Typs.

---

## Backlog

| # | Aufgabe | Status |
| :--- | :--- | :--- |
| 1 | Playbook-Detail-Seite auf getPlaybook(id) umstellen, Mock entfernen | ✅ |
| 2 | Docs: roadmap, requirements_gap, next_steps (Playbook-Detail, Activity-Timeline) | ✅ |
| 3 | Backend: POST /documents/bulk (mehrere Dateien, gleicher Typ) | ✅ |
| 4 | Frontend: Upload-Zone Mehrfachauswahl, Bulk-Request bei gleichem Typ | ✅ |

---

## Folgesprint (optional)

- Audit-Log (Check-Läufe, Finding-Status protokollieren); Activity-Timeline an echte API.
- Cross-Document-Checks (Multi-Dokument-Kontext im Check Runner).
