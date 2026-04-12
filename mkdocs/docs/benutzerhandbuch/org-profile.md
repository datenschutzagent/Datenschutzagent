# Org-Profile: Konfiguration für Ihre Organisation

Ein **Org-Profile** ist eine Konfigurationsdatei (YAML), die es ermöglicht, den DatenschutzAgent für verschiedene Organisationen zu konfigurieren, **ohne Code zu ändern**.

---

## Was ist ein Org-Profile?

Ein Org-Profile definiert:
- **Organisationsname** und -metadaten
- **Fachbereiche / Departments** (z. B. Uni-Fakultäten, Behörden-Abteilungen)
- **Benutzer** (optional, für lokale Tests)
- **Konfigurationsspezifika** (Playbooks, Templates, etc.)

Das System wird über die `ORG_PROFILE`-Umgebungsvariable auf ein bestimmtes Profile konfiguriert.

---

## Verfügbare vordefinierte Profile

### 1. **default** (Generisch)
Die **minimale** Konfiguration. Geeignet für:
- Testumgebungen
- Neue Organisationen ohne Spezialisierung

**Pfad:** `backend/app/data/org_profiles/default/`

### 2. **goethe** (Goethe-Universität Frankfurt)
Ein Universitäts-Profil mit:
- **16 Fachbereiche** (FB 01–16) + zentrale Einrichtungen
- **Spezialisierte Playbooks** für Uni-Compliance (AVV-Prüfung, Forschungsdaten-DSFA)
- **Departments:** Akademische und Administrative Einheiten

**Pfad:** `backend/app/data/org_profiles/goethe/`

### 3. **example** (Demonstrationsprofil)
Zu Demonstrationszwecken mit beispielhaften Daten.

---

## Org-Profile erstellen

### Verzeichnisstruktur
```
backend/app/data/org_profiles/
├── default/
│   ├── departments.yaml
│   ├── org_config.yaml (optional)
│   └── ...
├── goethe/
│   ├── departments.yaml
│   ├── org_config.yaml
│   └── playbooks/ (optional)
└── your-org/              # NEUES PROFILE
    ├── departments.yaml
    └── org_config.yaml (optional)
```

### 1. Departments-Datei erstellen

**Datei:** `backend/app/data/org_profiles/your-org/departments.yaml`

```yaml
# Departments / Fachbereiche für Ihre Organisation

departments:
  # Akademische Bereiche
  - code: "FB01"
    label: "Fachbereich 01 – Rechtswissenschaft"
    type: "faculty"
    value: "fb_01"
    
  - code: "FB02"
    label: "Fachbereich 02 – Wirtschaftswissenschaften"
    type: "faculty"
    value: "fb_02"

  # Zentrale Einrichtungen
  - code: "ZE01"
    label: "IT-Abteilung"
    type: "central"
    value: "it_department"
    
  - code: "ZE02"
    label: "Datenschutz"
    type: "central"
    value: "data_protection"

# Optional: Mehr Metadaten
metadata:
  organization_type: "university"  # university, company, public_authority
  location: "Frankfurt am Main"
  country: "DE"
```

### 2. Org-Config-Datei erstellen (optional)

**Datei:** `backend/app/data/org_profiles/your-org/org_config.yaml`

```yaml
# Organisationskonfiguration

organization:
  name: "Goethe-Universität Frankfurt"
  short_name: "GU Frankfurt"
  domain: "goethe-university.de"
  
  # Kontaktinformationen
  contact:
    dso: "dso@goethe-university.de"        # Data Security Officer
    dsb: "dsb@goethe-university.de"        # Data Protection Officer
    it_security: "security@goethe-university.de"

  # Rollen und Berechtigungen
  roles:
    admin:
      display_name: "Administrator"
      can_manage_users: true
      can_manage_settings: true
    
    editor:
      display_name: "Editor"
      can_edit_cases: true
      can_run_checks: true
    
    viewer:
      display_name: "Leser"
      can_view_only: true

# Playbook-Einstellungen
playbooks:
  # Welche Playbooks werden automatisch geladen?
  auto_import_dirs:
    - "/path/to/custom/playbooks"
  
  # Standard-Playbooks pro Department
  defaults:
    "fb_01": ["auftragsverarbeitung-audit", "datenschutz-basics"]
    "it_department": ["it-sicherheit", "datenschutz-basics"]

# Feature-Flags
features:
  dsr_management: true
  avv_management: true
  data_breach_reporting: true
  dsfa_management: true
  tom_management: true
  rag_enabled: true
  weaviate_enabled: false

# Richtlinien
policies:
  case_retention_days: 730          # 2 Jahre
  document_retention_days: 2555     # 7 Jahre (typisch für Archive)
  findings_export_allowed: true
  annotation_export_allowed: true
```

### 3. Profile aktivieren

**Datei:** `.env`
```bash
# Org-Profile auswählen
ORG_PROFILE=your-org

# Optional: Organisationsname im Frontend
ORG_NAME="Goethe-Universität Frankfurt"

# Optional: Playbooks von anderem Verzeichnis laden
PLAYBOOKS_SEED_DIR=/custom/playbooks
```

---

## Departments definieren

### Struktur
```yaml
departments:
  - code: "FB01"                    # Eindeutiger Code
    label: "Fachbereich 01 – Recht" # Anzeigename
    type: "faculty"                 # faculty | central | department | other
    value: "fb_01"                  # Interne ID (wird in Cases verwendet)
    description: "Die rechtliche Fakultät"  # Optional
    email: "fb01@example.com"       # Optional
```

### Typische Organisationstypen
- **Universität:** Fachbereiche (faculties) + zentrale Einrichtungen (central)
- **Behörde:** Abteilungen (departments)
- **Unternehmen:** Bereiche (departments) + Funktionen (functions)

### Goethe-Universität Beispiel
```yaml
departments:
  # Fachbereiche 01–16
  - code: "FB01"
    label: "Fachbereich 01 – Rechtswissenschaft"
    type: "faculty"
    value: "fb_01"
  
  # ... FB02 bis FB16 ...

  # Zentrale Einrichtungen
  - code: "ZE-Präs"
    label: "Präsidium"
    type: "central"
    value: "ze_praesidium"
  
  - code: "ZE-HRZ"
    label: "Hochschulrechenzentrum (HRZ)"
    type: "central"
    value: "ze_hrz"
    email: "hrz@uni-frankfurt.de"
```

---

## Playbooks und Templates

### Auto-Import bei Start
Wenn das Verzeichnis `backend/app/data/playbooks/` leer ist oder nicht existiert, werden Playbooks aus `PLAYBOOKS_SEED_DIR` automatisch beim Start importiert.

**Datei:** `backend/app/data/org_profiles/your-org/playbooks/mein-playbook.yaml`
```yaml
name: "Auftragsverarbeitung-Audit"
version: "1.0"
department: "ZE-Datenschutz"
case_type: "audit"

checks:
  - name: "AVV vorhanden?"
    instruction: "Prüfe, ob für diesen Dienstleister ein Auftragsverarbeitungsvertrag existiert."
    instruction_en: "Check if a Data Processing Agreement exists for this processor."
    scope: "document"
    severity: "high"
  
  - name: "AVV aktuell?"
    instruction: "Ist der AVV aktuell und nicht älter als 3 Jahre?"
    scope: "document"
    severity: "medium"
```

---

## Best Practices

### 1. Department-Struktur
- **Konsistente Codes:** z. B. `FB01`, `ZE01`, `DEP01`
- **Sprechende Names:** `FB01` → "Fachbereich 01 – Rechtswissenschaft"
- **Eindeutige Values:** `fb_01`, `ze_datenschutz` (used in APIs/Databases)

### 2. Playbooks
- Speichern Sie organisationsspezifische Playbooks im Profil-Verzeichnis
- Verwenden Sie aussagekräftige Check-Namen
- Setzen Sie `severity` und `scope` korrekt

### 3. Feature-Flags
Nicht alle Features sind für alle Organisationen relevant:
```yaml
features:
  dsr_management: true        # Nur wenn DSR-Anfragen erwartet
  data_breach_reporting: true # Meldeobligationen
  rag_enabled: false          # Nur mit Weaviate
```

### 4. Konfiguration in Layern
```
Ebene 1: .env (global, secrets)
       ↓
Ebene 2: org_config.yaml (org-spezifisch)
       ↓
Ebene 3: Case/Playbook-Defaults (pro Case)
```

---

## Migration zwischen Profilen

### Datenaustausch
```bash
# Cases exportieren (JSON)
curl http://localhost:8000/api/v1/cases?export=json \
  -H "Authorization: Bearer $TOKEN" > cases.json

# In neuem Profil importieren
curl -X POST http://localhost:8000/api/v1/cases/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @cases.json
```

---

## Beispiel: Neues Profil für Behörde

**Datei:** `.env`
```bash
ORG_PROFILE=my-authority
ORG_NAME="Landesamt für Datenschutz"
```

**Datei:** `backend/app/data/org_profiles/my-authority/departments.yaml`
```yaml
departments:
  - code: "Abt01"
    label: "Abteilung 1 – Datenschutz"
    type: "department"
    value: "abt_01"
    email: "abt1@ldv.de"
  
  - code: "Abt02"
    label: "Abteilung 2 – IT-Sicherheit"
    type: "department"
    value: "abt_02"
  
  - code: "Abt03"
    label: "Abteilung 3 – Aufsicht"
    type: "department"
    value: "abt_03"
```

**Datei:** `backend/app/data/org_profiles/my-authority/org_config.yaml`
```yaml
organization:
  name: "Landesamt für Datenschutz BadenWürttemberg"
  domain: "lfdi.bwl.de"
  contact:
    dsb: "dsb@lfdi.bwl.de"

features:
  data_breach_reporting: true   # Wichtig für Behörden!
  dsr_management: true
  tom_management: true
```

---

## Troubleshooting

### Profile wird nicht geladen
```bash
# 1. .env prüfen
env | grep ORG_PROFILE

# 2. Verzeichnis prüfen
ls -la backend/app/data/org_profiles/your-org/

# 3. YAML-Syntaxfehler?
python -m yaml backend/app/data/org_profiles/your-org/departments.yaml
```

### Playbooks werden nicht importiert
```bash
# 1. Verzeichnis existiert?
ls -la backend/app/data/org_profiles/your-org/playbooks/

# 2. PLAYBOOKS_SEED_DIR prüfen
grep PLAYBOOKS_SEED_DIR .env

# 3. Manually trigger import (via API oder Logs prüfen)
```

---

## Weitere Ressourcen

- [Goethe-Profile Beispiel](../../backend/app/data/org_profiles/goethe/)
- [Default-Profile Beispiel](../../backend/app/data/org_profiles/default/)
