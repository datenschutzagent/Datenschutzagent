/**
 * German UI labels and badge colours for the API's enumerated values.
 *
 * The union types mirror the backend constants (`app/constants.py`); keep them in
 * sync with `lib/api/schema.ts` when the API changes. This module replaced the
 * label maps that used to live next to the prototype mock data.
 */

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
  critical:
    "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/50 dark:text-red-300 dark:border-red-800",
  high: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/50 dark:text-orange-300 dark:border-orange-800",
  medium:
    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900/50 dark:text-yellow-300 dark:border-yellow-800",
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
