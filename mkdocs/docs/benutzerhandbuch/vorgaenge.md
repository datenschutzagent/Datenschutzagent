# Vorgänge (Cases)

Vorgänge repräsentieren Forschungsvorhaben bzw. Datenschutz-Prüfvorgänge. Pro Vorgang können Metadaten (Titel, Fachbereich, Typ, Sprache, Status, Assignee) gepflegt, Dokumente hochgeladen und Playbook-Checks ausgeführt werden.

## Vorgang anlegen

1. Auf der Startseite oder der Vorgangsliste **„Neuer Vorgang“** wählen.
2. **Schritt 1:** Titel, Fachbereich (oder zentrale Einrichtung), Vorgangstyp und optional Sprache angeben.
3. **Schritt 2:** Ein Playbook zuordnen (optional, kann später geändert werden).
4. **Schritt 3 (optional):** Dokumente auswählen und einen Dokumenttyp für alle festlegen. Nach dem Anlegen des Vorgangs werden die Dateien per Bulk-Upload hochgeladen.
5. Mit **Erstellen** den Vorgang anlegen. Sie werden zur Vorgangsdetailseite weitergeleitet.

## Vorgang bearbeiten und löschen

- **Bearbeiten:** In der Vorgangsdetailseite (Tab „Übersicht“) können Titel, Status, Assignee und weitere Felder geändert werden (Button „Bearbeiten“ bzw. inline, je nach Implementierung).
- **Löschen:** Vorgang löschen entfernt den Vorgang inklusive zugehöriger Dokumente und Findings aus der Datenbank; gespeicherte Dateien im Storage werden mitgelöscht.

## Status und Assignee

Der Vorgangsstatus und ein optionaler Bearbeiter (Assignee) können in der Übersicht gesetzt werden. Die Activity-Timeline zeigt u. a. durchgeführte Playbook-Checks und Finding-Statusänderungen.

## Rechte

- **Rolle editor/admin:** Vorgänge anlegen, bearbeiten, löschen.
- **Rolle viewer:** Nur Lesen (kein „Neuer Vorgang“, kein Bearbeiten/Löschen).
