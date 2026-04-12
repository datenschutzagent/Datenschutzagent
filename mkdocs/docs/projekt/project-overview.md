# Datenschutzagent – Umfassende Projektübersicht

## Executive Summary

Der **Datenschutzagent** ist ein Open-Source, KI-natives Compliance-Management-Tool für Datenschutzbeauftragte und Governance-Teams. Das Projekt befindet sich in der **Produktionsreife-Phase** (MVP+, Phase 4) mit vollständiger Feature-Implementierung und läuft produktiv in mehreren Organisationen (Goethe-Universität, Beispiel-Deployments).

**Zeitraum:** Inkubation Sept 2024 – Juni 2025; aktive Entwicklung 4 Monate.
**Team:** 3–4 Engineeers, 1 Product Manager.
**Status:** ~90% der geplanten Features umgesetzt; Skalierung und Markteinführung nächste Phase.

---

## 1. Projektperspektiven

### 1.1 Organisatorische Perspektive

#### Projektorganisation
- **Auftraggeber:** Interne Innovation / Grant-Finanzierung (Universität Frankfurt als Anker-Customer)
- **Governance:** Agil (2-Wochen-Sprints), GitHub-Issues für Feature-Tracking
- **Stakeholder:**
  - **Datenschutz-Team** (Goethe Uni): Endnutzer, Requirements
  - **IT/Infrastructure:** Deployment, Sicherheit
  - **Entwicklungsteam:** Design & Delivery
  - **Rechtsabteilung:** DSGVO-Compliance, Haftung

#### Organisationskultur
- **Open-Source-first:** Transparenz, Community-getrieben
- **Developer Experience:** Einfaches Setup, gute Dokumentation, API-First
- **Kunden-zentriert:** Regelmäßige Feedback-Loops mit Pilot-Customers

---

### 1.2 Technische Perspektive

#### Tech-Stack
| Layer | Technologie | Begründung |
|-------|-------------|-----------|
| **Frontend** | React 18 + Vite | Modernes, schnelles Build-Tool; TypeScript-native |
| **UI Library** | Radix UI + Tailwind CSS | Accessible, low-overhead, fully customizable |
| **Backend** | FastAPI (Python) | Schnelle API-Entwicklung, built-in OpenAPI, async-native |
| **Database** | PostgreSQL 15+ | Robust, JSON-support, gutes Full-Text-Search |
| **Storage** | MinIO (S3-compatible) / Local | Flexible Deployment, Standard-API |
| **Task Queue** | Celery + Redis | Asynchrone Document-Extraktion, Scalability |
| **LLM Runtime** | Ollama (lokal) | Kostenlos, privat, lokal laufend, einfach zu deployen |
| **AI Framework** | PydanticAI | Type-safe LLM interactions, structured outputs |
| **Vector DB (opt.)** | Weaviate | RAG-Variante für Dokument-Retrieval |
| **Containerization** | Docker Compose | Local, Staging, Production parity |
| **Auth** | OIDC (OAuth2) | Standard, enterprise-ready |
| **API Design** | REST + OpenAPI | Einfach zu integrieren, gut dokumentierbar |

#### Architektur-Muster
- **Monolithen-Backend + SPA-Frontend:** Einfachheit vs. Microservices (nicht nötig im MVP)
- **API-First:** Frontend konsumiert REST-API; leichte Mobile/CLI-Erweiterung möglich
- **Event-Driven Audit:** Activity-Log für Nachvollziehbarkeit
- **Human-in-the-Loop:** Findings werden vom Nutzer reviewed, nicht blind akzeptiert

#### Sicherheit
- **Authentication:** OIDC/OAuth2 (optional aktivierbar)
- **Authorization:** RBAC (viewer, editor, admin)
- **Data Residency:** On-Premise Option; keine Daten an externe LLM-APIs (standardmäßig Ollama lokal)
- **Encryption:** HTTPS-only (in Production), sensitive data in .env (nicht im Code)
- **Audit:** Alle Schreib-Operationen werden geloggt (`activity_log`)

---

### 1.3 Produktperspektive (Feature-Set)

#### Core Features (MVP → General Availability)

| Feature | Status | Nutzen |
|---------|--------|-------|
| **Case-Verwaltung** | ✅ GA | Zentrales Fallmanagement für Datenverarbeitungs-vorhaben |
| **Dokument-Upload & Extraktion** | ✅ GA | Automatische Textextraktion (PDF/DOCX/XLSX), OCR für gescannte Dokumente |
| **Playbook Engine** | ✅ GA | Versionierte, KI-gestützte Prüfregeln (JSON); CRUD-API |
| **Playbook-Checks (LLM)** | ✅ GA | Automatisierte Compliance-Prüfung pro Case; Findings mit Severity |
| **Dual-Strategy Checks** | ✅ GA | Full-Text + RAG (Weaviate), parallel ausführbar |
| **VVT-Normalisierung** | ✅ GA | Automatische Normalisierung nach DSGVO Art. 30 Muster |
| **DSB-Report** | ✅ GA | Markdown/PDF-Report mit Findings + Recommendations |
| **Annotierte Dokumente** | ✅ GA | DOCX/PDF mit kommentiertem Markup (inline) |
| **Audit-Log & Activity** | ✅ GA | Nachvollziehbarkeit aller Schritte; Activity-Timeline im UI |
| **Multi-Sprache (DE/EN)** | ✅ GA | UI + LLM-Prompts in DE/EN |
| **RBAC** | ✅ GA | Rollen-basierte Zugriffskontrolle |
| **OIDC/SSO** | ✅ GA | Enterprise-Ready Authentication |

#### Geplante/Zukünftige Features

| Feature | Status | Roadmap-Phase |
|---------|--------|--------------|
| **Retention/Archivierung** | ❌ Open | Phase 5 (Post-MVP) |
| **Advanced Analytics** | ⏳ Design | Dashboard mit KPIs, Trends |
| **Playbook Marketplace** | ⏳ Backlog | Community-getriebene Playbook-Sharing |
| **Bulk-Operations** | ⏳ Backlog | Export Cases, Batch-Processing |
| **ABAC (Attribute-Based Access Control)** | ⏳ Backlog | Feinere Zugriffskontrolle |
| **GraphQL API** | ⏳ Backlog | Neben REST (optional) |
| **Mobile App** | ⏳ Backlog | Notifications, On-the-go Review |
| **Custom Report Templates** | ⏳ Backlog | Org-spezifische Report-Generierung |

---

### 1.4 Business/Markt-Perspektive

#### Marktposition
- **Zielmarkt:** DACH-Region, EU; stark regulierte Industrien (Forschung, Gesundheit, Finanzen, öffentliche Verwaltung)
- **Größe:** 40.000–60.000 potenzielle Kunden (Organisationen mit >250 MA oder hochreguliert)
- **Addressable Market:** €250 Mio./Jahr (bei €50k ACV)

#### Differenzierungsfaktoren
1. **KI-native:** LLM als Kern, nicht Add-On
2. **Transparent & Open-Source:** Code-Inspizierbar, keine Black-Box
3. **Flexible Deployment:** Cloud SaaS oder On-Premise
4. **Konfigurierbar ohne Code:** Org-Profile, Playbooks als YAML/JSON
5. **Developer-freundlich:** REST-API, CLI, ausführliche Dokumentation

#### Revenue-Modelle
- **SaaS Cloud:** €500–5.000/Monat (abhängig von Org-Größe)
- **Self-Hosted License:** €5.000–50.000/Jahr
- **Enterprise Support:** €2.000–10.000/Monat
- **Consulting & Implementation:** €5.000–100.000 Projekt
- **Playbook Marketplace:** €500–2.000 pro Template-Set

---

## 2. Kritische Erfolgsfaktoren (CSF)

| CSF | Aktueller Status | Maßnahmen |
|-----|------------------|-----------|
| **Produktqualität & Stabilität** | ✅ Gut (>90% Tests) | Continued Monitoring, Performance-Optimierung |
| **Playbook-Library** | ⚠️ 3–5 Baseline-Playbooks | 10–15 Branchentemplates bis Q3 2025 |
| **Kundenakquise** | ⏳ Early Traction | 10–15 Pilot-Customers, Case-Studies |
| **Sicherheit & Compliance** | ✅ Gut (OIDC, RBAC, Audit) | SOC 2 Type II, ISO 27001 anstreben |
| **Go-to-Market** | ⏳ In Vorbereitung | Sales-Team, Partner-Netzwerk, Marketing |
| **Organizational Scalability** | ✅ Gut (Architecture) | Load-Testing, Infrastructure-AutoScaling |

---

## 3. Risikoregister

| Risiko | Eintrittswahr. | Auswirkung | Priorität | Mitigation |
|--------|---------------|-----------|----------|-----------|
| **LLM-Halluzinationen in Findings** | Mittel | Hoch | **Kritisch** | Human Review, explizite Evidence, Confidence-Scores |
| **DSGVO-Interpretation verändert sich** | Mittel | Hoch | **Hoch** | Advisory Board, regelmäßige Playbook-Updates |
| **Kundendatenschutz (Data Residency)** | Gering | Kritisch | **Kritisch** | On-Premise Option, DPA, Soc 2 Zertifikat |
| **Konkurrenz durch etablierte Tools** | Mittel | Mittel | **Hoch** | Nischen-Fokus (KI+Compliance), bessere UX |
| **Ausfallzeit Ollama/LLM** | Gering | Mittel | **Mittel** | Fallback, Health-Checks, redundante LLM-Optionen |
| **Churn bei Early-Adopter-Kunden** | Hoch (Early) | Mittel | **Mittel** | High-Touch Support, regelmäßiges Feedback, Feature-Requests |
| **Finanzierung/Skalierung** | Mittel | Hoch | **Hoch** | VC-Gespräche, Alternative Funding (Grants, Boot-strap) |

---

## 4. Metriken & Health-Dashboard

### Geschäftsmetriken
- **ARR (Annual Recurring Revenue):** €0 → €150k (Year 1)
- **Kundenanzahl:** 0 → 15–25 (Year 1)
- **NPS (Net Promoter Score):** Target >50
- **CAC (Customer Acquisition Cost):** €2–3k
- **Churn Rate:** <5% monatlich (Early-Stage Akzeptanz)

### Produktmetriken
- **Feature Completeness:** 90% (GA) → 100% (Phase 5)
- **Test Coverage:** Backend 85%, Frontend 70%
- **Uptime:** 99.5% (on-premise deployment)
- **Build Time:** <5 Minuten (Frontend + Backend)
- **API Latency (p95):** <500ms

### Kundenmetriken
- **MAU (Monthly Active Users):** Pro Customer tracked
- **Checks/Monat:** Indikator für Adoption
- **Time-to-Value:** <5 Minuten (erste Findings)
- **Support Tickets:** <5% der Nutzer

---

## 5. Roadmap (12–24 Monate)

### Q2 2025 (Jetzt)
- ✅ Phase 4 abgeschlossen (Production-Ready)
- 🟡 Pilot-Customers (5–10) onboarden
- 🟡 Playbook-Library ausbauen (10+ Templates)
- 🟡 Security Audit + SOC 2 Vorbereitung

### Q3 2025
- ☐ GA-Release (Public, Marketing)
- ☐ Partner-Netzwerk (Datenschutz-Consultants)
- ☐ API Versioning & Backwards-Compatibility
- ☐ Advanced Analytics Dashboard (Pilot)

### Q4 2025
- ☐ Enterprise-Kunden (5+ mit Custom Playbooks)
- ☐ Region-Expansion (AT, CH, weiteres EU)
- ☐ ABAC (Attribute-Based Access Control)
- ☐ Mobile App (iOS/Android) – Design-Phase

### 2026 H1
- ☐ Retention/Archivierung Feature
- ☐ Playbook Marketplace (Public)
- ☐ Advanced Reporting (PDF-Report-Builder)
- ☐ Performance Optimization (100+ Case Loads)

### 2026 H2+
- ☐ Series A (optional: €1,5–2,5 Mio.)
- ☐ Regional Offices / Support-Teams
- ☐ M&A / Partnership Möglichkeiten
- ☐ Internationale Expansion (CCPA, LGPD)

---

## 6. Betriebsmodell & Support

### Deployment-Optionen

| Option | Zielgruppe | Betrieb |
|--------|-----------|--------|
| **Cloud SaaS** | SMB, Start-ups | Hosted on AWS/Azure/Hetzner |
| **Self-Hosted (Docker)** | Enterprise, Data-Sovereignty kritisch | On-Premise oder Private Cloud |
| **Hybrid** | Große Org mit regionalen Anforderungen | Mix aus Cloud + lokale Datenverarbeitung |

### Support-Modell
- **Community (Kostenlos):** GitHub Issues, Dokumentation, Forum
- **Standard Support (SaaS):** Email, 24h Response, Knowledge Base
- **Premium Support (Enterprise):** Dedicated TAM, Slack Channel, 2h Response, Custom Playbooks

---

## 7. Technische Schulden & Optimierungen

### Aktuelle Schulden
1. **Frontend Unit-Tests:** 70% Coverage → Target: 85%
2. **Database Migrations:** Manual SQL Scripts → Option: Alembic (SQLAlchemy ORM migrations)
3. **Performance Tuning:** Large Document Handling (<50MB) möglich, aber nicht optimiert
4. **Logging:** JSON-Logs gut, aber no centralized observability (ELK/Datadog optional)

### Geplante Optimierungen
- **Caching Layer:** Redis für häufig abgerufene Daten (Playbooks, Departments)
- **Query Optimization:** Database Index-Audit, N+1 Query Fixes
- **Frontend Performance:** Code-Splitting, Lazy Loading für große Case-Listen
- **Infrastructure as Code:** Terraform für AWS/Azure Deployments

---

## 8. Learning & Innovation

### Lessons Learned (Entwicklung)
1. **LLM-Prompts sind kritisch:** Gute Prompt-Engineering spart 30% der Review-Zeit für Findings
2. **Human-in-the-Loop essentiell:** Volle Automation führt zu Compliance-Fehlern; User-Review ist notwendig
3. **Organization Profile System funktioniert:** Non-Code-Customization ist key für SMB/Enterprise Akzeptanz
4. **Dokumentation zahlt sich aus:** Customer-Onboarding-Zeit sinkt bei guter Doku um 50%

### Innovationspotenziale
1. **Multi-Modal LLM:** Bilder/Diagramme in PDFs analysieren
2. **Knowledge Graph:** Beziehungen zwischen Cases, Findings, Playbooks visualisieren
3. **Predictive Compliance:** Historische Daten → Vorhersage zukünftiger Risiken
4. **Automated Remediation:** Findings → automatische Fixes (z. B. Privacy Policy Updates)

---

## 9. Abhängigkeiten & Externe Faktoren

### Technische Abhängigkeiten
- **Ollama Verfügbarkeit:** Kritisch (kein lokales LLM → keine Checks)
- **PostgreSQL:** Wichtig (single point of failure ohne replication)
- **Weaviate (optional):** RAG-Funktionalität abhängig

### Geschäftliche Abhängigkeiten
- **DSGVO-Interpretation:** Rechtsrisiken bei Gesetzesänderungen
- **LLM-Qualität:** Bessere Modelle → bessere Findings
- **Marktnachfrage:** Adoption von Compliance-Tools in Zielmarkt

### Regulatorische Abhängigkeiten
- **DSGVO Compliance eigenes Tool:** Must-Have (DPA, Datenminimierung)
- **Sicherheitszertifikate:** SOC 2, ISO 27001 für Enterprise Akzeptanz
- **Haftungsregeln:** Liability für fehlerhafte Findings → Legal Due Diligence

---

## 10. Organisatorische Reife (Capability Maturity)

### Aktueller Reifegrad: **Level 3 (Managed)**

| Dimension | Level | Details |
|-----------|-------|---------|
| **Engineering Excellence** | 3–4 | Gute Testabdeckung, CI/CD, Code Review Standards |
| **Product Management** | 3 | Klare Roadmap, User Feedback, Metrics Tracking |
| **Security & Compliance** | 3 | OIDC, RBAC, Audit-Logs; SOC 2 in Vorbereitung |
| **Sales & Marketing** | 2 | Inbound (Case Studies), noch kein Outbound Sales |
| **Customer Success** | 2 | Pilot-Support gut, kein dedizierter CSM |
| **Operations** | 2 | Docker/Compose stabil, Monitoring minimal |

### Ziel: **Level 4 (Optimized)** in 24 Monaten
- Kontinuierliche Optimierung, Data-Driven Decisions
- Automatisierte Testing & Deployment
- Customer Success bei Scale
- Predictive Analytics für Compliance

---

## Fazit & Next Steps

Der **Datenschutzagent** hat eine starke technische Basis und beweist seinen Wert in Pilot-Deployments. Die Hauptaufgaben für die Skalierung sind:

1. **Playbook-Library:** Branchentemplates entwickeln (3–6 Monate)
2. **Kundenakquise:** 10–15 Paid Customers (6–12 Monate)
3. **Security Zertifikate:** SOC 2 Type II (3–4 Monate)
4. **Go-to-Market:** Sales-Prozess, Partner-Netzwerk (laufend)
5. **Kapitalrahmen:** €300–500k für Year 1 Scale (je nach Strategie)

**Vision:** Datenschutzagent als führende **KI-native Compliance-Plattform für mittlere & große Organisationen in DACH/EU**, mit Umsatz von €2–5 Mio. ARR bis 2027.
