# API Reference – Erweiterte Endpoints

Dieses Dokument dokumentiert die neueren API-Endpoints für DSGVO-Compliance-Management (DSR, AVV, Datenpannen, DSFA, TOM, Datenschutzerklärungen, Case-Templates).

---

## DSR-Management (Datenschutzanfragen – Art. 15–22 DSGVO)

### Overview
Verwaltung von Anfragen betroffener Personen auf Auskunft, Berichtigung, Löschung, Portabilität und Widerspruch.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/dsr` | DSR-Anfragen auflisten (mit Filtern: status, request_type, assignee, overdue_only) |
| POST | `/api/v1/dsr` | Neue DSR-Anfrage erstellen |
| GET | `/api/v1/dsr/{id}` | Details einer DSR-Anfrage |
| PATCH | `/api/v1/dsr/{id}` | DSR aktualisieren (Status, Assignee, Anmerkungen) |
| DELETE | `/api/v1/dsr/{id}` | DSR löschen |
| GET | `/api/v1/dsr/{id}/activities` | Activity-Log der DSR |
| POST | `/api/v1/dsr/{id}/complete` | DSR als abgeschlossen markieren |

### Request-Typen
- `access` – Auskunftsanfrage (Art. 15)
- `rectification` – Berichtigung (Art. 16)
- `erasure` – Löschung / Recht auf Vergessenwerden (Art. 17)
- `restrict_processing` – Einschränkung (Art. 18)
- `portability` – Datenportabilität (Art. 20)
- `objection` – Widerspruch (Art. 21)

### Status-Codes
- `received` – Angemeldet
- `acknowledged` – Bestätigung versendet
- `in_progress` – In Bearbeitung
- `completed` – Abgeschlossen
- `refused` – Abgelehnt

### Deadline-Berechnung
Antwortfrist: **30 Tage** ab Eingang (Art. 12 Abs. 3 DSGVO). Das System setzt `deadline_date` automatisch auf `received_date + 30 Tage`.

### Beispiel-Anfrage
```bash
POST /api/v1/dsr/
Content-Type: application/json

{
  "request_type": "access",
  "requester_name": "Max Mustermann",
  "requester_email": "max@example.com",
  "description": "Anfrage auf Auskunft nach Art. 15 DSGVO",
  "department": "FB 03"
}
```

### Beispiel-Response
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "request_type": "access",
  "status": "received",
  "received_date": "2024-04-12T10:30:00Z",
  "deadline_date": "2024-05-12T10:30:00Z",
  "requester_name": "Max Mustermann",
  "requester_email": "max@example.com",
  "assignee": null,
  "notes": null,
  "created_at": "2024-04-12T10:30:00Z",
  "updated_at": "2024-04-12T10:30:00Z"
}
```

---

## AVV-Management (Auftragsverarbeitungsverträge – Art. 28 DSGVO)

### Overview
Verwaltung von Auftragsverarbeitungsverträgen mit Dienstleistern und Cloud-Providern.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/avv` | AVV-Verträge auflisten (Filter: status, department, partner_type, expiring_soon) |
| POST | `/api/v1/avv` | Neuen AVV-Vertrag erstellen |
| GET | `/api/v1/avv/{id}` | Details eines AVV-Vertrages |
| PATCH | `/api/v1/avv/{id}` | AVV aktualisieren (Status, Expiry-Datum, Attachments) |
| DELETE | `/api/v1/avv/{id}` | AVV löschen |

### Status-Codes
- `draft` – Entwurf
- `under_review` – In Überprüfung
- `signed` – Unterzeichnet
- `expired` – Abgelaufen
- `terminated` – Beendet

### Partner-Typen
- `cloud_provider` – Cloud-Services (AWS, Azure, Google Cloud, Nextcloud, …)
- `software_vendor` – Software-Dienstleister (Ticketing, Analytics, CRM)
- `logistics` – Versand/Logistik
- `other` – Sonstiges

### Ablaufreport
Query-Parameter `expiring_soon=true` liefert Verträge, die in den nächsten **90 Tagen** ablaufen.

### Beispiel-Request
```bash
POST /api/v1/avv/
Content-Type: application/json

{
  "partner_name": "CloudProvider XYZ",
  "partner_type": "cloud_provider",
  "processing_description": "Hosting, Datenbackup",
  "data_categories": ["Personendaten", "Universitätsdaten"],
  "department": "FB 03",
  "signed_date": "2023-01-01",
  "expiry_date": "2026-01-01",
  "status": "signed"
}
```

---

## Datenpannen-Management (Security Incidents – Art. 33/34 DSGVO)

### Overview
Tracking von Sicherheitsverletzungen mit personenbezogenen Daten und Meldepflicht-Management.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/data-breaches` | Datenpannen auflisten (Filter: status, risk_level, department, overdue_only) |
| POST | `/api/v1/data-breaches` | Neue Datenpanne melden |
| GET | `/api/v1/data-breaches/{id}` | Details einer Datenpanne |
| PATCH | `/api/v1/data-breaches/{id}` | Datenpanne aktualisieren (Status, Findings, Response-Actions) |
| DELETE | `/api/v1/data-breaches/{id}` | Datenpanne löschen |
| GET | `/api/v1/data-breaches/{id}/notification-status` | Status der Behördenmeldung |

### Status-Codes
- `received` – Panne erkannt/gemeldet
- `analyzed` – Analyse durchgeführt
- `reported` – Meldung versendet
- `resolved` – Behobene Situation

### Risk-Level
- `critical` – Schwerwiegende Verletzung, hohe Betroffenenzahl
- `high` – Erhebliches Risiko für Betroffene
- `medium` – Moderate Betroffenheit
- `low` – Minimales Risiko

### Meldepflicht (72h-Deadline)
Gemäß Art. 33 Abs. 1 DSGVO müssen Datenpannen der **Datenschutzbehörde innerhalb von 72 Stunden** nach Kenntnisnahme gemeldet werden. Das System berechnet automatisch:
- `notification_deadline = discovered_at + 72 Stunden`
- Warnung, wenn `notification_deadline` überschritten wird

### Beispiel-Request
```bash
POST /api/v1/data-breaches/
Content-Type: application/json

{
  "title": "Unbefugter Datenbankzugriff – Server XYZ",
  "description": "Sicherheitslücke in Datenbank ermöglichte Zugriff auf personenbezogene Studentendaten",
  "discovered_at": "2024-04-11T15:30:00Z",
  "affected_data_categories": ["Namen", "Matrikelnummern", "E-Mail-Adressen"],
  "affected_individuals_count": 234,
  "risk_level": "high",
  "department": "IT-Sicherheit",
  "response_actions": ["Sicherheitslücke geschlossen", "Passwords zurückgesetzt", "Betroffene benachrichtigt"]
}
```

---

## DSFA-Management (Datenschutz-Folgenabschätzung – Art. 35–37)

### Overview
Verwaltung von Datenschutz-Folgenabschätzungen für Verarbeitungen mit hohem Risiko.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/dsfa` | DSFA-Dokumente auflisten (Filter: status, case_id) |
| POST | `/api/v1/dsfa` | Neue DSFA erstellen |
| GET | `/api/v1/dsfa/{id}` | Details einer DSFA |
| PATCH | `/api/v1/dsfa/{id}` | DSFA aktualisieren (Risikoanalyse, Maßnahmen) |
| DELETE | `/api/v1/dsfa/{id}` | DSFA löschen |
| POST | `/api/v1/dsfa/{id}/approve` | DSFA genehmigen |
| GET | `/api/v1/dsfa/{id}/export` | DSFA als PDF/DOCX exportieren |

### Struktur einer DSFA
```json
{
  "id": "uuid",
  "case_id": "uuid",
  "title": "DSFA für Forschungsprojekt XYZ",
  "processing_description": "Verarbeitung von Patientendaten für Studie",
  "legal_basis": ["Art. 6 Abs. 1 Buchst. a) DSGVO"],
  "data_categories": ["Gesundheitsdaten", "Pseudonymisierte ID"],
  "recipients": ["Forschungspartner A", "Universität B"],
  "retention_period": "5 Jahre",
  "risks": [
    {
      "id": "risk-1",
      "description": "Unbefugter Zugriff auf sensitive Patientendaten",
      "severity": "high",
      "affected_interests": ["Datenschutz", "Reputation"],
      "measures": [
        {"id": "m1", "description": "Verschlüsselung bei Übertragung", "status": "implemented"},
        {"id": "m2", "description": "Zugriffskontrolle (RBAC)", "status": "planned"}
      ]
    }
  ],
  "status": "in_progress",
  "approved_by": null,
  "created_at": "2024-04-10T09:00:00Z",
  "updated_at": "2024-04-12T14:00:00Z"
}
```

---

## TOM-Management (Technische und Organisatorische Maßnahmen – Art. 32)

### Overview
Dokumentation und Tracking von Sicherheits- und Datenschutzmaßnahmen.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/tom` | TOM-Maßnahmen auflisten (Filter: status, category, case_id) |
| POST | `/api/v1/tom` | Neue Maßnahme erstellen |
| GET | `/api/v1/tom/{id}` | Details einer Maßnahme |
| PATCH | `/api/v1/tom/{id}` | Maßnahme aktualisieren (Status, Implementierungsdatum, Evidence) |
| DELETE | `/api/v1/tom/{id}` | Maßnahme löschen |

### Kategorien
- `encryption` – Verschlüsselung (in Transit / at Rest)
- `access_control` – Zugriffskontrolle (RBAC, MFA)
- `logging` – Audit-Logging und Monitoring
- `backup` – Datensicherung
- `incident_response` – Incident-Response-Plan
- `data_deletion` – Datenlöschungs-Prozess
- `training` – Datenschutz-Schulungen
- `vulnerability_management` – Patch-Management, Schwachstelle-Scanning
- `other` – Sonstiges

### Status
- `planned` – Geplant
- `in_progress` – In Umsetzung
- `implemented` – Implementiert
- `verified` – Überprüft
- `not_applicable` – Nicht anwendbar

### Beispiel-TOM
```json
{
  "id": "uuid",
  "title": "Verschlüsselung von Datenbanken",
  "category": "encryption",
  "description": "AES-256-Verschlüsselung für alle PostgreSQL-Datenbanken",
  "status": "implemented",
  "responsible": "IT-Sicherheit",
  "target_date": "2024-06-01",
  "implementation_date": "2024-04-01",
  "evidence": "Zertifikat_Verschlüsselung.pdf",
  "case_id": "uuid"
}
```

---

## Privacy Policy Management (Datenschutzerklärungen)

### Overview
Datenschutzerklärungen sind **vorgangsspezifisch**: jede Erklärung gehört zu
genau einem Case (Verarbeitungstätigkeit). Pro Case sind mehrere Versionen
möglich; die Versionsnummer wird automatisch hochgezählt.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/cases/{case_id}/privacy-policies` | Versionen für einen Vorgang auflisten |
| POST | `/api/v1/cases/{case_id}/privacy-policies/generate` | Neue Version generieren (LLM, basiert auf Case-Daten) |
| GET | `/api/v1/privacy-policies` | Globale read-only Übersicht aller Erklärungen |
| GET | `/api/v1/privacy-policies/{id}` | Einzelne Erklärung abrufen |
| PATCH | `/api/v1/privacy-policies/{id}` | Titel/Inhalt/Versionsnotiz bearbeiten |
| DELETE | `/api/v1/privacy-policies/{id}` | Einzelne Version löschen (admin) |

Wird ein Case gelöscht, werden alle zugehörigen Datenschutzerklärungen via
`ON DELETE CASCADE` mit entfernt.

### Inhaltsbestandteile
Eine Erklärung beschreibt **eine konkrete Verarbeitungstätigkeit** und enthält:
- Verantwortlicher (Art. 13/14 DSGVO)
- Verarbeitungszweck und Rechtsgrundlage genau dieser Tätigkeit
- Kategorien personenbezogener Daten in dieser Verarbeitung
- Empfänger / Auftragsverarbeiter (sofern relevant)
- Speicherdauer (aus `retention_months` des Case)
- Hinweise auf Art.-9-Daten und Drittlandtransfer, falls zutreffend
- Betroffenenrechte (Auskunft, Berichtigung, Löschung, …)
- Beschwerderecht bei Behörde

---

## Case-Templates (Vorlagen für neue Vorgänge)

### Overview
Vorlagen für standardisierte Case-Typen mit vorkonfiguriertem Playbook und Fragen.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/case-templates` | Alle Case-Templates auflisten |
| POST | `/api/v1/case-templates` | Neues Template erstellen (Admin only) |
| GET | `/api/v1/case-templates/{id}` | Details eines Templates |
| POST | `/api/v1/cases/from-template/{template_id}` | Neuen Case aus Template erstellen |

### Vordefinierte Templates
- **Auftragsverarbeitung-Audit** – Prüfung von AVV-Verträgen
- **Datenschutz-Folgenabschätzung** – DSFA-Vorlage
- **Datenpanne-Response** – Incident-Management
- **Neue Verarbeitung** – Generische Compliance-Prüfung

---

## Webhooks (Event-Notifications)

### Overview
Webhook-Support für automatische Benachrichtigungen bei wichtigen Events.

| Methode | Pfad | Beschreibung |
| :--- | :--- | :--- |
| GET | `/api/v1/webhooks` | Registrierte Webhooks auflisten |
| POST | `/api/v1/webhooks` | Neuen Webhook registrieren |
| PATCH | `/api/v1/webhooks/{id}` | Webhook aktualisieren (Activate/Deactivate) |
| DELETE | `/api/v1/webhooks/{id}` | Webhook löschen |
| GET | `/api/v1/webhooks/{id}/deliveries` | Zustellverlauf |

### Unterstützte Events
- `case.created` – Neuer Case angelegt
- `case.updated` – Case aktualisiert
- `finding.created` – Neues Finding
- `dsr.received` – Neue DSR-Anfrage
- `dsr.deadline_approaching` – DSR-Deadline in 7 Tagen
- `data_breach.reported` – Datenpanne gemeldet
- `avv.expiring_soon` – AVV läuft bald ab
- `dsfa.needs_approval` – DSFA wartet auf Genehmigung

### Payload-Format
```json
{
  "event": "case.created",
  "timestamp": "2024-04-12T14:30:00Z",
  "data": {
    "case_id": "550e8400-e29b-41d4-a716-446655440000",
    "case_title": "Auftragsverarbeitung-Audit",
    "case_type": "audit",
    "created_by": "admin@example.com"
  }
}
```

### Retry-Logik
Webhook-Zustellungen werden **3x versucht** mit exponentiellem Backoff (1s, 2s, 4s). Fehlgeschlagene Zustellungen werden im Zustellverlauf protokolliert.

---

## Allgemeine Hinweise

### Authentication
Alle Endpoints erfordern einen **Bearer-Token** (JWT), außer:
- `GET /api/v1/auth/config`
- `GET /health`

### RBAC (Role-Based Access Control)
| Endpoint-Typ | Erforderliche Rolle |
| :--- | :--- |
| Lesen (GET) | `viewer`, `editor`, `admin` |
| Schreiben (POST, PATCH) | `editor`, `admin` |
| Löschen (DELETE) | `admin` |
| Admin-Endpoints (`/admin/*`) | `admin` |

### Error-Responses
```json
{
  "detail": "Insufficient permissions",
  "type": "authorization_error",
  "status_code": 403
}
```

### Pagination
GET-Endpoints mit Listenfunktion unterstützen:
- `skip` (Standard: 0)
- `limit` (Standard: 100, Max: 500)

---

## Swagger/ReDoc
Interaktive API-Dokumentation:
- **Swagger UI:** `/docs`
- **ReDoc:** `/redoc`
