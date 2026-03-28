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

export type ActivityType = 
  | "case_created"
  | "document_uploaded"
  | "document_updated"
  | "status_changed"
  | "playbook_run"
  | "finding_status_changed"
  | "comment_added"
  | "deadline_set"
  | "deadline_changed"
  | "assigned";

export type Priority = "low" | "medium" | "high" | "urgent";

export interface Activity {
  id: string;
  caseId: string;
  type: ActivityType;
  timestamp: string;
  performedBy: string;
  description: string;
  metadata?: {
    oldValue?: string;
    newValue?: string;
    documentName?: string;
    findingId?: string;
    comment?: string;
  };
}

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
  priority?: Priority;
  deadline?: string;
  tags?: string[];
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
    title: "Einführung CRM-System",
    department: "IT",
    caseType: "IT-System",
    status: "in_review",
    createdAt: "2026-01-15",
    updatedAt: "2026-02-05",
    createdBy: "Dr. Schmidt",
    assignee: "DSB Team",
    language: "de_en",
    playbookVersion: "v2.3.0",
    priority: "high",
    deadline: "2026-02-15",
    tags: ["Klinische Studie", "Burnout", "Art. 9 DSGVO"],
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
    priority: "low",
    deadline: "2026-02-28",
    tags: ["Archiv", "Historie"],
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
    title: "Personalverarbeitung Onboarding",
    department: "HR",
    caseType: "HR",
    status: "questions_pending",
    createdAt: "2026-01-28",
    updatedAt: "2026-02-06",
    createdBy: "Dr. Weber",
    assignee: "DSB Team",
    language: "en",
    playbookVersion: "v2.3.1",
    priority: "urgent",
    deadline: "2026-02-10",
    tags: ["KI/ML", "Gesundheitsdaten", "DSFA", "Drittland"],
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
    name: "IT-Systeme Prüfung",
    version: "v2.3.0",
    department: "IT",
    caseType: "IT-System",
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
    name: "Personaldaten HR",
    version: "v2.3.1",
    department: "HR",
    caseType: "HR",
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
    name: "Standard Datenschutzprüfung (generisch)",
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
  intake: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  in_review: "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300",
  questions_pending: "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300",
  revision: "bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300",
  ready_for_decision: "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300",
  completed: "bg-gray-100 text-gray-500 dark:bg-slate-800 dark:text-slate-400",
};

export const severityColors: Record<FindingSeverity, string> = {
  critical: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/50 dark:text-red-300 dark:border-red-800",
  high: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/50 dark:text-orange-300 dark:border-orange-800",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/50 dark:text-yellow-300 dark:border-yellow-800",
  low: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/50 dark:text-blue-300 dark:border-blue-800",
  info: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
};

export const severityLabels: Record<FindingSeverity, string> = {
  critical: "Kritisch",
  high: "Hoch",
  medium: "Mittel",
  low: "Niedrig",
  info: "Info",
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

export const priorityLabels: Record<Priority, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  urgent: "Dringend",
};

export const priorityColors: Record<Priority, string> = {
  low: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  medium: "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300",
  urgent: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300",
};

export const activityTypeLabels: Record<ActivityType, string> = {
  case_created: "Vorgang erstellt",
  document_uploaded: "Dokument hochgeladen",
  document_updated: "Dokument aktualisiert",
  status_changed: "Status geändert",
  playbook_run: "Playbook ausgeführt",
  finding_status_changed: "Finding-Status geändert",
  comment_added: "Kommentar hinzugefügt",
  deadline_set: "Frist gesetzt",
  deadline_changed: "Frist geändert",
  assigned: "Zugewiesen",
};

// Mock Activities
export const mockActivities: Activity[] = [
  // Activities for case-001
  {
    id: "act-001",
    caseId: "case-001",
    type: "case_created",
    timestamp: "2026-01-15T09:23:00Z",
    performedBy: "Dr. Schmidt",
    description: "Vorgang erstellt",
  },
  {
    id: "act-002",
    caseId: "case-001",
    type: "document_uploaded",
    timestamp: "2026-01-15T09:45:00Z",
    performedBy: "Dr. Schmidt",
    description: "Dokument hochgeladen: Schwellenwertanalyse_v1.docx",
    metadata: {
      documentName: "Schwellenwertanalyse_v1.docx",
    },
  },
  {
    id: "act-003",
    caseId: "case-001",
    type: "document_uploaded",
    timestamp: "2026-01-15T09:47:00Z",
    performedBy: "Dr. Schmidt",
    description: "Dokument hochgeladen: Probandeninformation_DE.pdf",
    metadata: {
      documentName: "Probandeninformation_DE.pdf",
    },
  },
  {
    id: "act-004",
    caseId: "case-001",
    type: "document_uploaded",
    timestamp: "2026-01-15T09:48:00Z",
    performedBy: "Dr. Schmidt",
    description: "Dokument hochgeladen: Participant_Information_EN.pdf",
    metadata: {
      documentName: "Participant_Information_EN.pdf",
    },
  },
  {
    id: "act-005",
    caseId: "case-001",
    type: "document_uploaded",
    timestamp: "2026-01-15T10:12:00Z",
    performedBy: "Dr. Schmidt",
    description: "Dokument hochgeladen: VVT_Burnout_Studie_v1.xlsx",
    metadata: {
      documentName: "VVT_Burnout_Studie_v1.xlsx",
    },
  },
  {
    id: "act-006",
    caseId: "case-001",
    type: "deadline_set",
    timestamp: "2026-01-15T10:30:00Z",
    performedBy: "DSB Team",
    description: "Frist gesetzt auf 15.02.2026",
    metadata: {
      newValue: "2026-02-15",
    },
  },
  {
    id: "act-007",
    caseId: "case-001",
    type: "playbook_run",
    timestamp: "2026-01-15T11:00:00Z",
    performedBy: "System",
    description: "Playbook ausgeführt: Klinische Forschung (Psychologie) v2.3.0",
  },
  {
    id: "act-008",
    caseId: "case-001",
    type: "status_changed",
    timestamp: "2026-01-15T11:05:00Z",
    performedBy: "System",
    description: "Status geändert: Intake → In Vorprüfung",
    metadata: {
      oldValue: "Intake",
      newValue: "In Vorprüfung",
    },
  },
  {
    id: "act-009",
    caseId: "case-001",
    type: "comment_added",
    timestamp: "2026-01-20T14:22:00Z",
    performedBy: "DSB Team",
    description: "Kommentar hinzugefügt",
    metadata: {
      comment: "VVT Version 1 unvollständig - Rückmeldung an Antragsteller gesendet.",
    },
  },
  {
    id: "act-010",
    caseId: "case-001",
    type: "document_updated",
    timestamp: "2026-02-03T16:15:00Z",
    performedBy: "Dr. Schmidt",
    description: "Dokument aktualisiert: VVT_Burnout_Studie_v2.xlsx (Version 2)",
    metadata: {
      documentName: "VVT_Burnout_Studie_v2.xlsx",
    },
  },
  {
    id: "act-011",
    caseId: "case-001",
    type: "playbook_run",
    timestamp: "2026-02-03T16:30:00Z",
    performedBy: "System",
    description: "Playbook erneut ausgeführt nach Dokumenten-Update",
  },
  {
    id: "act-012",
    caseId: "case-001",
    type: "finding_status_changed",
    timestamp: "2026-02-05T10:10:00Z",
    performedBy: "DSB Team",
    description: "Finding-Status geändert: find-001 → Behoben",
    metadata: {
      findingId: "find-001",
      oldValue: "Offen",
      newValue: "Behoben",
    },
  },
  
  // Activities for case-002
  {
    id: "act-101",
    caseId: "case-002",
    type: "case_created",
    timestamp: "2026-01-20T11:15:00Z",
    performedBy: "Prof. Müller",
    description: "Vorgang erstellt",
  },
  {
    id: "act-102",
    caseId: "case-002",
    type: "document_uploaded",
    timestamp: "2026-01-20T11:30:00Z",
    performedBy: "Prof. Müller",
    description: "Dokument hochgeladen: VVT_Archivdigitalisierung.docx",
    metadata: {
      documentName: "VVT_Archivdigitalisierung.docx",
    },
  },
  {
    id: "act-103",
    caseId: "case-002",
    type: "document_uploaded",
    timestamp: "2026-01-20T11:32:00Z",
    performedBy: "Prof. Müller",
    description: "Dokument hochgeladen: DSFA_Screening.pdf",
    metadata: {
      documentName: "DSFA_Screening.pdf",
    },
  },
  {
    id: "act-104",
    caseId: "case-002",
    type: "deadline_set",
    timestamp: "2026-01-20T11:40:00Z",
    performedBy: "DSB Team",
    description: "Frist gesetzt auf 28.02.2026",
    metadata: {
      newValue: "2026-02-28",
    },
  },
  {
    id: "act-105",
    caseId: "case-002",
    type: "playbook_run",
    timestamp: "2026-01-20T12:00:00Z",
    performedBy: "System",
    description: "Playbook ausgeführt: Archivprojekte (Geschichte) v2.1.0",
  },
  {
    id: "act-106",
    caseId: "case-002",
    type: "status_changed",
    timestamp: "2026-01-20T12:05:00Z",
    performedBy: "System",
    description: "Status geändert: Intake → In Vorprüfung",
    metadata: {
      oldValue: "Intake",
      newValue: "In Vorprüfung",
    },
  },
  {
    id: "act-107",
    caseId: "case-002",
    type: "finding_status_changed",
    timestamp: "2026-02-02T15:20:00Z",
    performedBy: "DSB Team",
    description: "Finding-Status geändert: find-101 → Akzeptiert",
    metadata: {
      findingId: "find-101",
      oldValue: "Offen",
      newValue: "Akzeptiert",
    },
  },
  {
    id: "act-108",
    caseId: "case-002",
    type: "status_changed",
    timestamp: "2026-02-04T09:30:00Z",
    performedBy: "DSB Team",
    description: "Status geändert: In Vorprüfung → Entscheidungsvorlage",
    metadata: {
      oldValue: "In Vorprüfung",
      newValue: "Entscheidungsvorlage",
    },
  },
  {
    id: "act-109",
    caseId: "case-002",
    type: "comment_added",
    timestamp: "2026-02-04T09:35:00Z",
    performedBy: "DSB Team",
    description: "Kommentar hinzugefügt",
    metadata: {
      comment: "Keine datenschutzrechtlichen Bedenken. Kann freigegeben werden.",
    },
  },

  // Activities for case-003
  {
    id: "act-201",
    caseId: "case-003",
    type: "case_created",
    timestamp: "2026-01-28T08:45:00Z",
    performedBy: "Dr. Weber",
    description: "Vorgang erstellt",
  },
  {
    id: "act-202",
    caseId: "case-003",
    type: "document_uploaded",
    timestamp: "2026-01-28T09:00:00Z",
    performedBy: "Dr. Weber",
    description: "Dokument hochgeladen: Patient_Information_Sheet.pdf",
    metadata: {
      documentName: "Patient_Information_Sheet.pdf",
    },
  },
  {
    id: "act-203",
    caseId: "case-003",
    type: "document_uploaded",
    timestamp: "2026-01-28T09:15:00Z",
    performedBy: "Dr. Weber",
    description: "Dokument hochgeladen: ROPA_AI_Diagnostics_v1.xlsx",
    metadata: {
      documentName: "ROPA_AI_Diagnostics_v1.xlsx",
    },
  },
  {
    id: "act-204",
    caseId: "case-003",
    type: "deadline_set",
    timestamp: "2026-01-28T10:00:00Z",
    performedBy: "DSB Team",
    description: "Frist gesetzt auf 10.02.2026",
    metadata: {
      newValue: "2026-02-10",
    },
  },
  {
    id: "act-205",
    caseId: "case-003",
    type: "document_uploaded",
    timestamp: "2026-02-01T11:20:00Z",
    performedBy: "Dr. Weber",
    description: "Dokument hochgeladen: DPIA_Draft_v1.docx",
    metadata: {
      documentName: "DPIA_Draft_v1.docx",
    },
  },
  {
    id: "act-206",
    caseId: "case-003",
    type: "document_updated",
    timestamp: "2026-02-03T14:30:00Z",
    performedBy: "Dr. Weber",
    description: "Dokument aktualisiert: Threshold_Analysis.docx (Version 2)",
    metadata: {
      documentName: "Threshold_Analysis.docx",
    },
  },
  {
    id: "act-207",
    caseId: "case-003",
    type: "document_uploaded",
    timestamp: "2026-02-04T10:45:00Z",
    performedBy: "Dr. Weber",
    description: "Dokument hochgeladen: DPA_CloudML_Provider.pdf",
    metadata: {
      documentName: "DPA_CloudML_Provider.pdf",
    },
  },
  {
    id: "act-208",
    caseId: "case-003",
    type: "document_updated",
    timestamp: "2026-02-05T16:00:00Z",
    performedBy: "Dr. Weber",
    description: "Dokument aktualisiert: ROPA_AI_Diagnostics_v3.xlsx (Version 3)",
    metadata: {
      documentName: "ROPA_AI_Diagnostics_v3.xlsx",
    },
  },
  {
    id: "act-209",
    caseId: "case-003",
    type: "playbook_run",
    timestamp: "2026-02-05T16:30:00Z",
    performedBy: "System",
    description: "Playbook ausgeführt: Medizinische Forschung (high-risk) v2.3.1",
  },
  {
    id: "act-210",
    caseId: "case-003",
    type: "status_changed",
    timestamp: "2026-02-06T09:00:00Z",
    performedBy: "DSB Team",
    description: "Status geändert: In Vorprüfung → Rückfragen ausstehend",
    metadata: {
      oldValue: "In Vorprüfung",
      newValue: "Rückfragen ausstehend",
    },
  },
  {
    id: "act-211",
    caseId: "case-003",
    type: "comment_added",
    timestamp: "2026-02-06T09:15:00Z",
    performedBy: "DSB Team",
    description: "Kommentar hinzugefügt",
    metadata: {
      comment: "Kritische Findings zur DSFA und AVV. Rückfragen an Antragsteller versendet. Deadline verlängern?",
    },
  },
];