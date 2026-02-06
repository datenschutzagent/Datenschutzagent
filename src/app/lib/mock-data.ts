// Mock data for the Data Protection Agent prototype

export type CaseStatus = 
  | "intake" 
  | "in_review" 
  | "questions_pending" 
  | "revision" 
  | "ready_for_decision" 
  | "completed";

export type DocumentType = 
  | "vvt" 
  | "screening" 
  | "info_sheet_de" 
  | "info_sheet_en" 
  | "dsfa" 
  | "avv" 
  | "other";

export type FindingSeverity = "critical" | "high" | "medium" | "low" | "info";

export type FindingStatus = "open" | "accepted" | "overruled" | "fixed";

export interface Document {
  id: string;
  name: string;
  type: DocumentType;
  version: number;
  uploadedAt: string;
  uploadedBy: string;
  size: string;
  format: "docx" | "pdf" | "xlsx" | "doc";
}

export interface Finding {
  id: string;
  checkName: string;
  severity: FindingSeverity;
  status: FindingStatus;
  category: string;
  description: string;
  evidence: string[];
  recommendation: string;
  documentId?: string;
}

export interface Case {
  id: string;
  title: string;
  department: string;
  caseType: string;
  status: CaseStatus;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  assignee: string;
  language: "de" | "en" | "de_en";
  documents: Document[];
  findings: Finding[];
  playbookVersion: string;
}

export interface PlaybookCheck {
  id: string;
  name: string;
  description: string;
  type: "document" | "cross_document";
  category: string;
  mandatory: boolean;
  targetDocuments: DocumentType[];
}

export interface Playbook {
  id: string;
  name: string;
  version: string;
  department: string;
  caseType: string;
  createdAt: string;
  updatedAt: string;
  status: "draft" | "active" | "archived";
  checks: PlaybookCheck[];
}

export const mockCases: Case[] = [
  {
    id: "case-001",
    title: "Longitudinalstudie zur Burnout-Prävention",
    department: "Psychologie",
    caseType: "clinical_study",
    status: "in_review",
    createdAt: "2026-01-15",
    updatedAt: "2026-02-05",
    createdBy: "Dr. Schmidt",
    assignee: "DSB Team",
    language: "de_en",
    playbookVersion: "v2.3.0",
    documents: [
      {
        id: "doc-001",
        name: "VVT_Burnout_Studie_v2.xlsx",
        type: "vvt",
        version: 2,
        uploadedAt: "2026-02-03",
        uploadedBy: "Dr. Schmidt",
        size: "145 KB",
        format: "xlsx",
      },
      {
        id: "doc-002",
        name: "Schwellenwertanalyse_v1.docx",
        type: "screening",
        version: 1,
        uploadedAt: "2026-01-15",
        uploadedBy: "Dr. Schmidt",
        size: "89 KB",
        format: "docx",
      },
      {
        id: "doc-003",
        name: "Probandeninformation_DE.pdf",
        type: "info_sheet_de",
        version: 1,
        uploadedAt: "2026-01-15",
        uploadedBy: "Dr. Schmidt",
        size: "210 KB",
        format: "pdf",
      },
      {
        id: "doc-004",
        name: "Participant_Information_EN.pdf",
        type: "info_sheet_en",
        version: 1,
        uploadedAt: "2026-01-15",
        uploadedBy: "Dr. Schmidt",
        size: "198 KB",
        format: "pdf",
      },
    ],
    findings: [
      {
        id: "find-001",
        checkName: "VVT Pflichtfeld: Zwecke der Verarbeitung",
        severity: "high",
        status: "fixed",
        category: "VVT Vollständigkeit",
        description: "Feld 'Zwecke der Verarbeitung' war in Version 1 nicht ausgefüllt.",
        evidence: ["VVT_Burnout_Studie_v1.xlsx, Zeile 12, Spalte C"],
        recommendation: "Konkrete Forschungszwecke dokumentieren.",
        documentId: "doc-001",
      },
      {
        id: "find-002",
        checkName: "Art. 13 DSGVO: Speicherdauer fehlt",
        severity: "critical",
        status: "open",
        category: "Informationspflichten",
        description: "Die Speicherdauer oder Kriterien zu deren Festlegung fehlen im Informationsblatt.",
        evidence: ["Probandeninformation_DE.pdf, Seite 2"],
        recommendation: "Bitte ergänzen Sie die Speicherdauer gemäß Forschungsplan (z.B. '10 Jahre nach Projektende').",
        documentId: "doc-003",
      },
      {
        id: "find-003",
        checkName: "DSFA-Schwelle: Systematische Überwachung",
        severity: "medium",
        status: "accepted",
        category: "DSFA Screening",
        description: "Die Schwellenwertanalyse deutet auf eine systematische Überwachung hin (Längschnittstudie mit Tracking).",
        evidence: ["Schwellenwertanalyse_v1.docx, Abschnitt 3.2"],
        recommendation: "DSFA erforderlich. Bitte vollständige DSFA-Dokumentation einreichen.",
        documentId: "doc-002",
      },
      {
        id: "find-004",
        checkName: "Konsistenz: Rechtsgrundlage VVT ↔ Info Sheet",
        severity: "high",
        status: "open",
        category: "Cross-Document Konsistenz",
        description: "Im VVT ist Art. 6 Abs. 1 lit. e angegeben, im Info Sheet wird jedoch von 'Einwilligung' gesprochen.",
        evidence: [
          "VVT_Burnout_Studie_v2.xlsx, Zeile 15",
          "Probandeninformation_DE.pdf, Seite 1, Absatz 3"
        ],
        recommendation: "Bitte Rechtsgrundlage klären und konsistent darstellen.",
      },
      {
        id: "find-005",
        checkName: "AVV: Dienstleister in den USA",
        severity: "high",
        status: "open",
        category: "Auftragsverarbeitung",
        description: "Im VVT ist ein Cloud-Provider (USA) als Empfänger genannt, jedoch kein AVV hochgeladen.",
        evidence: ["VVT_Burnout_Studie_v2.xlsx, Zeile 22: 'CloudProvider Inc., USA'"],
        recommendation: "AVV und TOMs sowie Drittlandtransfer-Garantien (z.B. SCCs) erforderlich.",
        documentId: "doc-001",
      },
    ],
  },
  {
    id: "case-002",
    title: "Archivdigitalisierung mittelalterlicher Handschriften",
    department: "Geschichte",
    caseType: "archival_project",
    status: "ready_for_decision",
    createdAt: "2026-01-20",
    updatedAt: "2026-02-04",
    createdBy: "Prof. Müller",
    assignee: "DSB Team",
    language: "de",
    playbookVersion: "v2.1.0",
    documents: [
      {
        id: "doc-101",
        name: "VVT_Archivdigitalisierung.docx",
        type: "vvt",
        version: 1,
        uploadedAt: "2026-01-20",
        uploadedBy: "Prof. Müller",
        size: "92 KB",
        format: "docx",
      },
      {
        id: "doc-102",
        name: "DSFA_Screening.pdf",
        type: "screening",
        version: 1,
        uploadedAt: "2026-01-20",
        uploadedBy: "Prof. Müller",
        size: "134 KB",
        format: "pdf",
      },
    ],
    findings: [
      {
        id: "find-101",
        checkName: "DSFA nicht erforderlich",
        severity: "info",
        status: "accepted",
        category: "DSFA Screening",
        description: "Keine personenbezogenen Daten im Sinne der DSGVO betroffen (historische Quellen >100 Jahre).",
        evidence: ["DSFA_Screening.pdf, Seite 1"],
        recommendation: "Keine weitere DSFA notwendig. Bitte VVT als 'nicht anwendbar' kennzeichnen.",
        documentId: "doc-102",
      },
    ],
  },
  {
    id: "case-003",
    title: "KI-gestützte Diagnose seltener Erkrankungen",
    department: "Medizin",
    caseType: "medical_research",
    status: "questions_pending",
    createdAt: "2026-01-28",
    updatedAt: "2026-02-06",
    createdBy: "Dr. Weber",
    assignee: "DSB Team",
    language: "en",
    playbookVersion: "v2.3.1",
    documents: [
      {
        id: "doc-201",
        name: "ROPA_AI_Diagnostics_v3.xlsx",
        type: "vvt",
        version: 3,
        uploadedAt: "2026-02-05",
        uploadedBy: "Dr. Weber",
        size: "201 KB",
        format: "xlsx",
      },
      {
        id: "doc-202",
        name: "Threshold_Analysis.docx",
        type: "screening",
        version: 2,
        uploadedAt: "2026-02-03",
        uploadedBy: "Dr. Weber",
        size: "112 KB",
        format: "docx",
      },
      {
        id: "doc-203",
        name: "Patient_Information_Sheet.pdf",
        type: "info_sheet_en",
        version: 1,
        uploadedAt: "2026-01-28",
        uploadedBy: "Dr. Weber",
        size: "167 KB",
        format: "pdf",
      },
      {
        id: "doc-204",
        name: "DPIA_Draft_v1.docx",
        type: "dsfa",
        version: 1,
        uploadedAt: "2026-02-01",
        uploadedBy: "Dr. Weber",
        size: "389 KB",
        format: "docx",
      },
      {
        id: "doc-205",
        name: "DPA_CloudML_Provider.pdf",
        type: "avv",
        version: 1,
        uploadedAt: "2026-02-04",
        uploadedBy: "Dr. Weber",
        size: "1.2 MB",
        format: "pdf",
      },
    ],
    findings: [
      {
        id: "find-201",
        checkName: "DSFA: Risikobewertung unvollständig",
        severity: "critical",
        status: "open",
        category: "DSFA Vollständigkeit",
        description: "Die Risikobewertung für KI-basierte Verarbeitung sensibler Gesundheitsdaten ist unvollständig.",
        evidence: ["DPIA_Draft_v1.docx, Abschnitt 4.2"],
        recommendation: "Bitte konkrete Eintrittswahrscheinlichkeiten und Schadenshöhen bewerten.",
        documentId: "doc-204",
      },
      {
        id: "find-202",
        checkName: "AVV: TOMs-Anlage fehlt",
        severity: "high",
        status: "open",
        category: "Auftragsverarbeitung",
        description: "Der AVV enthält keinen separaten Anhang mit technischen und organisatorischen Maßnahmen.",
        evidence: ["DPA_CloudML_Provider.pdf, Seite 1-8 (kein TOMs-Anhang gefunden)"],
        recommendation: "TOMs-Anlage gemäß Art. 28 Abs. 3 lit. c DSGVO anfordern.",
        documentId: "doc-205",
      },
      {
        id: "find-203",
        checkName: "Info Sheet: Widerrufsrecht unklar",
        severity: "medium",
        status: "open",
        category: "Informationspflichten",
        description: "Das Widerrufsrecht der Einwilligung ist nicht deutlich formuliert.",
        evidence: ["Patient_Information_Sheet.pdf, Seite 3"],
        recommendation: "Ergänzen Sie: 'You can withdraw your consent at any time without giving reasons. The withdrawal does not affect the lawfulness of processing based on consent before its withdrawal.'",
        documentId: "doc-203",
      },
    ],
  },
];

export const mockPlaybooks: Playbook[] = [
  {
    id: "pb-001",
    name: "Klinische Forschung (Psychologie)",
    version: "v2.3.0",
    department: "Psychologie",
    caseType: "clinical_study",
    createdAt: "2025-09-10",
    updatedAt: "2026-01-15",
    status: "active",
    checks: [
      {
        id: "check-001",
        name: "VVT Pflichtfeld: Zwecke der Verarbeitung",
        description: "Prüft, ob die Zwecke der Verarbeitung konkret benannt sind.",
        type: "document",
        category: "VVT Vollständigkeit",
        mandatory: true,
        targetDocuments: ["vvt"],
      },
      {
        id: "check-002",
        name: "VVT Pflichtfeld: Rechtsgrundlage",
        description: "Prüft, ob eine Rechtsgrundlage gemäß Art. 6 DSGVO angegeben ist.",
        type: "document",
        category: "VVT Vollständigkeit",
        mandatory: true,
        targetDocuments: ["vvt"],
      },
      {
        id: "check-003",
        name: "Art. 13 DSGVO: Informationspflichten vollständig",
        description: "Prüft Vollständigkeit der Angaben nach Art. 13 DSGVO im Informationsblatt.",
        type: "document",
        category: "Informationspflichten",
        mandatory: true,
        targetDocuments: ["info_sheet_de", "info_sheet_en"],
      },
      {
        id: "check-004",
        name: "DSFA-Schwellenwertanalyse",
        description: "Prüft, ob aufgrund der Schwellenwertanalyse eine DSFA erforderlich ist.",
        type: "document",
        category: "DSFA Screening",
        mandatory: true,
        targetDocuments: ["screening"],
      },
      {
        id: "check-005",
        name: "Konsistenz: Rechtsgrundlage VVT ↔ Info Sheet",
        description: "Gleicht die Rechtsgrundlage zwischen VVT und Informationsblatt ab.",
        type: "cross_document",
        category: "Cross-Document Konsistenz",
        mandatory: true,
        targetDocuments: ["vvt", "info_sheet_de", "info_sheet_en"],
      },
      {
        id: "check-006",
        name: "AVV bei Drittlandtransfer",
        description: "Prüft, ob bei genannten Empfängern außerhalb EU/EWR ein AVV vorhanden ist.",
        type: "cross_document",
        category: "Auftragsverarbeitung",
        mandatory: true,
        targetDocuments: ["vvt", "avv"],
      },
      {
        id: "check-007",
        name: "Besondere Kategorien personenbezogener Daten",
        description: "Prüft, ob bei Verarbeitung von Art. 9 DSGVO-Daten eine zusätzliche Rechtsgrundlage genannt ist.",
        type: "document",
        category: "VVT Vollständigkeit",
        mandatory: true,
        targetDocuments: ["vvt"],
      },
    ],
  },
  {
    id: "pb-002",
    name: "Medizinische Forschung (high-risk)",
    version: "v2.3.1",
    department: "Medizin",
    caseType: "medical_research",
    createdAt: "2025-10-01",
    updatedAt: "2026-01-20",
    status: "active",
    checks: [
      {
        id: "check-101",
        name: "DSFA: Risikobewertung vorhanden",
        description: "Prüft, ob eine vollständige Risikobewertung in der DSFA vorliegt.",
        type: "document",
        category: "DSFA Vollständigkeit",
        mandatory: true,
        targetDocuments: ["dsfa"],
      },
      {
        id: "check-102",
        name: "AVV: TOMs-Anlage",
        description: "Prüft, ob der AVV eine Anlage mit technischen und organisatorischen Maßnahmen enthält.",
        type: "document",
        category: "Auftragsverarbeitung",
        mandatory: true,
        targetDocuments: ["avv"],
      },
      {
        id: "check-103",
        name: "Info Sheet: Einwilligung und Widerruf",
        description: "Prüft, ob Einwilligung und Widerrufsrecht klar formuliert sind.",
        type: "document",
        category: "Informationspflichten",
        mandatory: true,
        targetDocuments: ["info_sheet_de", "info_sheet_en"],
      },
      {
        id: "check-104",
        name: "VVT ↔ DSFA Konsistenz: Kategorien betroffener Personen",
        description: "Gleicht die genannten Personengruppen zwischen VVT und DSFA ab.",
        type: "cross_document",
        category: "Cross-Document Konsistenz",
        mandatory: true,
        targetDocuments: ["vvt", "dsfa"],
      },
    ],
  },
  {
    id: "pb-003",
    name: "Archivprojekte (Geschichte)",
    version: "v2.1.0",
    department: "Geschichte",
    caseType: "archival_project",
    createdAt: "2025-08-15",
    updatedAt: "2025-11-10",
    status: "active",
    checks: [
      {
        id: "check-201",
        name: "DSFA: Nicht erforderlich bei historischen Quellen",
        description: "Prüft, ob personenbezogene Daten betroffen sind (historische Quellen >100 Jahre meist nicht relevant).",
        type: "document",
        category: "DSFA Screening",
        mandatory: true,
        targetDocuments: ["screening"],
      },
      {
        id: "check-202",
        name: "VVT: Archivierungszweck dokumentiert",
        description: "Prüft, ob der Zweck der Archivierung klar benannt ist.",
        type: "document",
        category: "VVT Vollständigkeit",
        mandatory: true,
        targetDocuments: ["vvt"],
      },
    ],
  },
  {
    id: "pb-004",
    name: "Standard Forschungsvorhaben (generisch)",
    version: "v1.8.2",
    department: "Alle",
    caseType: "general_research",
    createdAt: "2025-06-01",
    updatedAt: "2025-09-20",
    status: "archived",
    checks: [
      {
        id: "check-301",
        name: "VVT Basisfelder vorhanden",
        description: "Prüft minimale Pflichtfelder im VVT.",
        type: "document",
        category: "VVT Vollständigkeit",
        mandatory: true,
        targetDocuments: ["vvt"],
      },
    ],
  },
];

export const statusLabels: Record<CaseStatus, string> = {
  intake: "Intake",
  in_review: "In Vorprüfung",
  questions_pending: "Rückfragen ausstehend",
  revision: "Revision",
  ready_for_decision: "Entscheidungsvorlage",
  completed: "Abgeschlossen",
};

export const statusColors: Record<CaseStatus, string> = {
  intake: "bg-slate-100 text-slate-700",
  in_review: "bg-blue-100 text-blue-700",
  questions_pending: "bg-amber-100 text-amber-700",
  revision: "bg-purple-100 text-purple-700",
  ready_for_decision: "bg-green-100 text-green-700",
  completed: "bg-gray-100 text-gray-500",
};

export const severityColors: Record<FindingSeverity, string> = {
  critical: "bg-red-100 text-red-700 border-red-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
  low: "bg-blue-100 text-blue-700 border-blue-200",
  info: "bg-slate-100 text-slate-700 border-slate-200",
};

export const findingStatusLabels: Record<FindingStatus, string> = {
  open: "Offen",
  accepted: "Akzeptiert",
  overruled: "Überfahren",
  fixed: "Behoben",
};

export const documentTypeLabels: Record<DocumentType, string> = {
  vvt: "VVT / ROPA",
  screening: "Schwellenwertanalyse",
  info_sheet_de: "Informationsblatt DE",
  info_sheet_en: "Informationsblatt EN",
  dsfa: "DSFA / DPIA",
  avv: "AVV / DPA",
  other: "Sonstiges",
};
