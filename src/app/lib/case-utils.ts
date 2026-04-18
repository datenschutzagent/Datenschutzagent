import type { ApiCase, ApiFinding } from "./api/cases";

export interface CaseStats {
  critical: number;
  high: number;
  fixed: number;
  total: number;
}

export function getCaseStats(findings: ApiFinding[]): CaseStats {
  return {
    critical: findings.filter(f => f.severity === "critical" && f.status === "open").length,
    high: findings.filter(f => f.severity === "high" && f.status === "open").length,
    fixed: findings.filter(f => f.status === "fixed").length,
    total: findings.length,
  };
}

export type DeadlineStatus = "overdue" | "soon" | "ok";

export function getDeadlineStatus(deadline?: string): DeadlineStatus | null {
  if (!deadline) return null;
  const daysUntil = Math.ceil((new Date(deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  if (daysUntil < 0) return "overdue";
  if (daysUntil <= 3) return "soon";
  return "ok";
}

export function formatDeadline(deadline: string): string {
  return new Date(deadline).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function getStatsForCase(caseItem: ApiCase): CaseStats {
  return getCaseStats(caseItem.findings);
}
