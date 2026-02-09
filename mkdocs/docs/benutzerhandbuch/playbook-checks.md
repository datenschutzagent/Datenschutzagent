# Playbook-Checks ausführen

„Playbook-Checks ausführen“ (Run-Checks) startet die KI-gestützte Prüfung der Vorgangsdokumente anhand eines gewählten Playbooks. Die Ergebnisse werden als **Findings** gespeichert und im Tab „Findings“ angezeigt.

## Ablauf

1. **Vorgang öffnen** (Case-Detailseite).
2. **„Playbook-Checks ausführen“** (bzw. „Checks starten“) wählen.
3. **Playbook** auswählen.
4. **Strategie** wählen (falls RAG aktiv):
   - **Volltext:** Der (gekürzte) Volltext jedes Dokuments wird an das LLM übergeben (klassisch).
   - **RAG:** Es werden relevante Textabschnitte aus der Vektordatenbank (Weaviate) abgerufen und nur diese an das LLM übergeben.
   - **Beide:** Beide Strategien parallel; Findings werden mit `source_strategy` (Volltext/RAG) gekennzeichnet, zum Vergleich.
5. **Start** auslösen. Der Lauf kann je nach Dokumentanzahl und Modell einige Zeit dauern. Ein Status-Endpoint (`GET /cases/{id}/run-checks/status`) erlaubt optional Polling.

## Ergebnis

- **Findings:** Pro Check und ggf. Dokument (oder pro Case bei Cross-Document-Checks) entstehen Findings mit Compliance-Status, Severity, Evidence und Empfehlung. Sie erscheinen im Tab „Findings“; bei Cross-Document-Checks mit „Vorgangsbezogen“ gekennzeichnet.
- **Activity-Timeline:** Jeder Run-Check wird im Aktivitätslog erfasst (Playbook-Version, Modell, Anzahl Findings; bei Fehlern oder übersprungenen Checks auch `errors` und `skipped_checks_count`).

## Voraussetzungen

- **Ollama** muss laufen und unter `OLLAMA_BASE_URL` erreichbar sein.
- Rolle **editor** oder **admin** erforderlich.
