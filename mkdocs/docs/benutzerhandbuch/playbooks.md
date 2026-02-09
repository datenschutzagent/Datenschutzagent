# Playbooks

Playbooks sind versionierte Prüfregeln: Eine Liste von Checks (Name, Anweisung/Instruction), die beim „Playbook-Checks ausführen“ gegen die Dokumente eines Vorgangs laufen. Sie können Fachbereich und Vorgangstyp zuordnen.

## Playbook-Liste und -Detail

- **Playbooks-Seite:** Zeigt alle Playbooks. Über „Neues Playbook“ kann ein Playbook angelegt werden (Rolle editor/admin).
- **Playbook-Detail:** Einzelnes Playbook anzeigen, bearbeiten, archivieren, löschen oder duplizieren. Bearbeiten/Löschen/Duplizieren nur mit Rolle editor/admin.

## Standard-Playbooks (YAML)

Die Anwendung bringt Standard-Playbooks als YAML-Dateien mit (Fachbereiche und zentrale Einrichtungen). Beim **ersten Start** werden diese automatisch importiert, wenn die Playbook-Tabelle leer ist. Der Inhalt liegt unter `backend/app/data/playbooks/`. Ein Playbook-YAML enthält u. a. `name`, `version`, `department`, optional `case_type` und eine Liste `checks` mit `name`, `instruction` und optional `instruction_en` (für englische Cases) sowie optional `scope` (document/case für Cross-Document-Checks).

## Anlegen und Bearbeiten

- **Anlegen:** Dialog „Neues Playbook“ mit Name, Version, optional Fachbereich/Vorgangstyp und Inhalt (JSON/Struktur der Checks).
- **Bearbeiten:** Im Playbook-Detail „Bearbeiten“ wählen; Änderungen werden über die API gespeichert.
- **Archivieren/Löschen:** Über die Aktionen im Playbook-Detail. Gelöschte Playbooks stehen für neue Run-Checks nicht mehr zur Verfügung.

## Duplizieren

Ein bestehendes Playbook kann dupliziert werden, um eine Kopie als Ausgangsbasis für ein neues Playbook zu nutzen (Rolle editor/admin).
