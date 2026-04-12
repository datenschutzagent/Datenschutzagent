# Datenschutz-Konzepte und DSGVO-Basics

Dieser Bereich erklärt die wichtigsten datenschutzrechtlichen Konzepte, die im **DatenschutzAgent** implementiert sind.

---

## Überblick der DSGVO-Konzepte

| Kürzel | Vollform | Art. | Bedeutung |
| :--- | :--- | :--- | :--- |
| **DSB** | Datenschutzbeauftragte/r | 37–39 | Verantwortliche Person für Datenschutz-Compliance |
| **DSR** | Datenschutzanfrage (Betroffenenrecht) | 15–22 | Anfragen von Personen auf Auskunft, Berichtigung, Löschung, Portabilität, Widerspruch |
| **AVV** | Auftragsverarbeitungsvertrag | 28 | Vertragswerk mit Auftragsverarbeitern (z. B. Cloud-Provider, Dienstleister) |
| **DSFA** | Datenschutz-Folgenabschätzung | 35–37 | Risikoanalyse bei Verarbeitung mit hohem Risiko |
| **TOM** | Technische und Organisatorische Maßnahmen | 32–34 | Sicherheits- und Datenschutzvorkehrungen |
| **VVT** | Verzeichnis von Verarbeitungstätigkeiten | 30 | Dokumentation aller Datenverarbeitungen (Art. 30 DSGVO) |
| **Datenpanne** | Sicherheitsverletzung mit personenbezogenen Daten | 33–34 | Meldeobligation an Behörde (72h) und ggf. an Betroffene |

---

## 1. Datenschutzbeauftragte (DSB)

### Rolle und Verantwortung
Ein **Datenschutzbeauftragter** ist gemäß Art. 37 DSGVO zu bestellen, wenn:
- Eine öffentliche Stelle Datenverarbeitung durchführt
- Ein Unternehmen Datenverarbeitung als Kerntätigkeit durchführt  
- Regelmäßige, systematische Überwachung von Personen stattfindet

### Im DatenschutzAgent
Der **Admin-Bereich** (Verwaltung, Rollen) ermöglicht es dem DSB/Administrator:
- **Fachbereiche und Departments** zu konfigurieren
- **Benutzer und Rollen** zu verwalten (Viewer, Editor, Admin)
- **Playbooks** (Audit-Checklisten) zu erstellen und zu verwalten
- **DSB-Reports** zu generieren (Case-Status, Findings, Empfehlungen)
- **Compliance-Status** per VVT-Normalisierung nachzuverfolgen

---

## 2. Datenschutzanfragen (DSR – Art. 15–22 DSGVO)

### Was sind DSR?
**Datenschutzanfragen** sind Anfragen von betroffenen Personen auf:
- **Auskunft** (Art. 15) – Welche Daten wurden über mich verarbeitet?
- **Berichtigung** (Art. 16) – Falsche Daten korrigieren
- **Löschung** (Art. 17) – „Recht auf Vergessenwerden"
- **Einschränkung** (Art. 18) – Verarbeitung pausieren
- **Datenportabilität** (Art. 20) – Daten in maschinenlesbarem Format exportieren
- **Widerspruch** (Art. 21) – Verarbeitung zurückweisen (z. B. Marketing)

### Deadline und Status
- **Antwortfrist:** 30 Tage ab Eingang (ggf. um 60 Tage verlängerbar)
- **Status-Tracking:** Im DatenschutzAgent können DSR-Anfragen registriert und deren Status verfolgtwarden
  - `received` → `acknowledged` → `in_progress` → `completed` oder `refused`

### Im DatenschutzAgent
Das **DSR-Management** (`/dsr`-Endpunkte) ermöglicht:
- DSR-Anfragen auflisten, filtern (Status, Typ, Assignee, Fälligkeitsdatum)
- Anfrage erstellen und aktualisieren
- **Deadline-Tracking:** Fälligkeitsdatum (30 Tage) automatisch berechnet
- **Activity-Log:** Alle Aktivitäten zur DSR-Anfrage nachverfolgen

---

## 3. Auftragsverarbeitungsverträge (AVV – Art. 28 DSGVO)

### Was ist eine AVV?
Eine **Auftragsverarbeitungsvereinbarung** ist ein Vertrag zwischen:
- **Verantwortliche** (z. B. Universität) und
- **Auftragsverarbeiter** (z. B. Cloud-Provider, Dienstleister)

Sie regelt:
- Welche Daten verarbeitet werden
- Wo und wie lange
- Sicherheitsstandards
- Subauftragsverarbeiter
- Löschpflichten nach Vertragsendenverbindlich.

### Partner-Typen
- **Cloud-Provider** (AWS, Azure, Google Cloud, Nextcloud, …)
- **Software-Dienstleister** (Ticketing-Systeme, Analytics, …)
- **Versand/Logistik**
- **Sonstiges**

### Im DatenschutzAgent
Das **AVV-Management** ermöglicht:
- AVV-Verträge erfassen und organisieren
- **Ablauffristen** verwalten (automatische Warnung 90 Tage vor Ablauf)
- **Compliance-Status** pro Bereich/Department
- **Dokumentation:** PDF/Attachments speichern

---

## 4. Datenschutz-Folgenabschätzung (DSFA – Art. 35–37)

### Zweck
Die DSFA ist eine systematische Risikoanalyse, die vor Beginn einer **Verarbeitung mit hohem Risiko** durchgeführt werden muss. Sie dokumentiert:
- Verarbeitete Daten und Datenquellen
- Rechtsgrundlagen
- Beteiligte (Verantwortlicher, Auftragsverarbeiter, Dritte)
- Risiken für die Rechte und Freiheiten von Personen
- **Geplante Sicherheitsmaßnahmen**

### Wann ist eine DSFA erforderlich?
- Automatisierte Einzelfallentscheidungen mit Rechtsfolgen (Art. 22)
- Großflächige Überwachung (Kameras, Tracking)
- Verarbeitung besonderer Kategorien (Gesundheit, Biometrie, …) in großem Ausmaß
- Innovative Technologien mit Datenschutzrisiko

### Im DatenschutzAgent
Das **DSFA-Management** unterstützt:
- DSFA-Vorlagen und -Fragekataloge
- Strukturierte Erfassung der Risiken (High/Medium/Low)
- Maßnahmen-Tracking (TOM)
- Verknüpfung zu Cases und Findings

---

## 5. Technische und Organisatorische Maßnahmen (TOM – Art. 32–34)

### Definition
**TOMs** sind Sicherheitsvorkehrungen, um personenbezogene Daten zu schützen. Sie umfassen:

| Kategorie | Beispiele |
| :--- | :--- |
| **Technisch** | Verschlüsselung, Zugriffskontrolle, Firewalls, Backups, Logging |
| **Organisatorisch** | Datenschutz-Schulungen, Richtlinien, Sicherheitsaudits, Incident-Response |

### Im DatenschutzAgent
Das **TOM-Management** dokumentiert:
- Geplante vs. implementierte Maßnahmen
- Status und Verantwortliche
- Verknüpfung zu DSFA/Cases
- Nachweis-Dokumentation (Screenshots, Zertifikate)

---

## 6. Verzeichnis von Verarbeitungstätigkeiten (VVT – Art. 30)

### Zweck
Das VVT ist eine **Dokumentation aller Datenverarbeitungen** einer Organisation. Es muss enthalten:
- Verarbeitungszweck
- Kategorien personenbezogener Daten
- Kategorien von Empfängern
- Speicherdauer
- Sicherheitsmaßnahmen

### Normalisierung
Der DatenschutzAgent bietet **VVT-Normalisierung**: Unstrukturierte Dokumente werden gescannt und in ein standardisiertes VVT-Format (DSGVO Art. 30) überführt.

### Im DatenschutzAgent
- **VVT-Übersicht:** Alle erfassten Verarbeitungen nach Abteilung/Prozess
- **VVT-Normalisierung:** LLM-gestützte Extraktion und Standardisierung  
- **VVT-Export:** CSV oder DOCX-Report (mit Template-Vorlagen)

---

## 7. Datenpannen (Security Incidents – Art. 33/34 DSGVO)

### Meldeobligation
Bei einer **Datenpanne** (Sicherheitsverletzung mit personenbezogenen Daten) muss die Organisation:
1. **Behörde melden** (Datenschutzbehörde/Landesamt): **72 Stunden** ab Kenntnisnahme
2. **Betroffene benachrichtigen:** bei hohem Risiko (Art. 34 DSGVO)

### Dokumentation
Das Dokument muss enthalten:
- Beschreibung der Panne
- Auswirkungen auf betroffene Personen
- Getroffene/geplante Maßnahmen

### Im DatenschutzAgent
Das **Datenpannen-Management** unterstützt:
- **Status-Tracking:** Received → Analyzed → Reported → Resolved
- **72h-Countdown:** Automatische Warnung bei Deadline-Überschreitung
- **Risk-Level:** Critical / High / Medium / Low
- **Benachrichtigungs-Audit-Log** (wer, wann, an wen benachrichtigt)

---

## 8. Compliance-Checklisten (Playbooks)

### Struktur eines Playbooks
Ein **Playbook** ist eine Checkliste mit **Checks** (Fragen/Anforderungen). Jeder Check:
- Hat einen Namen und eine Beschreibung  
- Kann sich auf Dokumente oder Cross-Document-Ebene beziehen
- Wird per LLM gegen die Case-Dokumente validiert
- Erzeugt **Findings** (Bestanden / Nicht bestanden / Warnung)

### Beispiele
- **Goethe-Universität-Playbook:** Auftragsverarbeitung (AVV), DSFA-Anforderungen, Datenschutz-Schulungen
- **Generisches Playbook:** Häufige DSGVO-Anforderungen

### Im DatenschutzAgent
- Playbooks können hochgeladen, versioniert und angepasst werden
- Run-Checks: Alle Checks eines Playbooks gegen einen Case ausführen
- Befunde werden mit `source_strategy` (full_text / rag) und Severity gekennzeichnet

---

## Häufige Abkürzungen

| Kürzel | Bedeutung |
| :--- | :--- |
| **DSGVO** | Datenschutz-Grundverordnung (EU 2016/679) |
| **BDSG** | Bundesdatenschutzgesetz (Deutschland) |
| **LDG** | Landesdatenschutzgesetz (Bundesländer) |
| **LFDI** | Landesbeauftragte/r für Datenschutz und Informationsfreiheit |
| **BfDI** | Bundesbeauftragte/r für Datenschutz und Informationsfreiheit |
| **ROI** | Risikoanalyse/Risikofolgenabschätzung |
| **ISMS** | Information Security Management System |
| **SLA** | Service Level Agreement (oft in AVV-Verträgen) |

---

## Weitere Ressourcen

- **Offizielle Guides:** [Europäischer Datenschutzausschuss – EDPB](https://edpb.ec.europa.eu/)
- **Bundesbeauftragter:** [BfDI](https://www.bfdi.bund.de/)
- **Text DSGVO:** [DSGVO auf EUR-Lex](https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32016R0679)
