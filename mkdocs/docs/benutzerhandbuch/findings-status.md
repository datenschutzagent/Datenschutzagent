# Findings und Status

Findings sind die strukturierten Prüfergebnisse eines Playbook-Checks: pro Check (und ggf. pro Dokument oder pro Vorgang bei Cross-Document-Checks) entsteht ein Eintrag mit Compliance, Severity, Evidence und Empfehlung.

## Anzeige

- **Tab „Findings“** in der Vorgangsdetailseite: Liste aller Findings des Vorgangs. Findings mit `document_id=null` (Case-Checks) werden als **„Vorgangsbezogen“** (Cross-Document) angezeigt.
- Optional **Badge** für die Strategie (Volltext / RAG), falls Run-Checks mit RAG oder „Beide“ ausgeführt wurden.

## Status setzen

Jedes Finding hat einen Status, der den Bearbeitungsstand abbildet:

- **open** – Offen
- **accepted** – Akzeptiert
- **overruled** – Überstimmt
- **fixed** – Behoben

In der UI können Sie den Status über Buttons oder ein Dropdown ändern (Rolle editor/admin). Die Änderung wird an die API (`PATCH /api/v1/findings/{id}`) gesendet und im Audit-Log (Activity-Timeline) als Event `finding_status_updated` festgehalten.

## Rechte

- **Rolle viewer:** Findings nur lesen, kein Status ändern.
- **Rolle editor/admin:** Status ändern.
