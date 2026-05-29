/**
 * RiskMatrix2D — ISO-27005-style 5×5 Risk Matrix (Likelihood × Severity).
 *
 * Renders a coloured grid where each cell shows the count of risks at that
 * likelihood/severity position. Hovering over a cell reveals the matching
 * risks as a tooltip.
 *
 * Used on the DSFA detail view to give DPOs an at-a-glance picture of the
 * risk distribution for a case.
 */
import { useMemo } from "react";

export type DsfaRisk = {
  description: string;
  likelihood: "low" | "medium" | "high";
  severity: "low" | "medium" | "high";
  mitigation: string;
  likelihood_score?: number | null;
  severity_score?: number | null;
  risk_level?: "low" | "medium" | "high" | "critical" | null;
};

const LEVEL_BG: Record<string, string> = {
  low: "bg-blue-100 dark:bg-blue-900/40 text-blue-900 dark:text-blue-100",
  medium: "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-900 dark:text-yellow-100",
  high: "bg-orange-100 dark:bg-orange-900/40 text-orange-900 dark:text-orange-100",
  critical: "bg-red-100 dark:bg-red-900/40 text-red-900 dark:text-red-100",
};

// Standard ISO-27005-style fallback matrix — used when the API does not yet
// expose the org-specific config. Mirrors the default in risk_config.yaml.
const FALLBACK_MATRIX: Record<string, string> = {
  "1_1": "low", "1_2": "low", "1_3": "low", "1_4": "medium", "1_5": "medium",
  "2_1": "low", "2_2": "low", "2_3": "medium", "2_4": "medium", "2_5": "high",
  "3_1": "low", "3_2": "medium", "3_3": "medium", "3_4": "high", "3_5": "high",
  "4_1": "medium", "4_2": "medium", "4_3": "high", "4_4": "high", "4_5": "critical",
  "5_1": "medium", "5_2": "high", "5_3": "high", "5_4": "critical", "5_5": "critical",
};

const DEFAULT_LIKELIHOOD_LABELS: Record<number, string> = {
  1: "sehr unwahrscheinlich",
  2: "unwahrscheinlich",
  3: "möglich",
  4: "wahrscheinlich",
  5: "sehr wahrscheinlich",
};
const DEFAULT_SEVERITY_LABELS: Record<number, string> = {
  1: "vernachlässigbar",
  2: "begrenzt",
  3: "spürbar",
  4: "erheblich",
  5: "maximal",
};

type Props = {
  risks: DsfaRisk[];
  matrix?: Record<string, string>;
  likelihoodLabels?: Record<number, string>;
  severityLabels?: Record<number, string>;
  /** Optional inherent risks (pre-mitigation). When present, each cell gets a
   * dashed inherent-count badge so the user can see how mitigations shifted
   * the risks. */
  inherentRisks?: DsfaRisk[];
};

export function RiskMatrix2D({ risks, matrix, likelihoodLabels, severityLabels, inherentRisks }: Props) {
  const cellMap = matrix ?? FALLBACK_MATRIX;
  const likLabels = likelihoodLabels ?? DEFAULT_LIKELIHOOD_LABELS;
  const sevLabels = severityLabels ?? DEFAULT_SEVERITY_LABELS;

  // Group risks by their (likelihood_score, severity_score) cell.
  const grouped = useMemo(() => {
    const acc: Record<string, DsfaRisk[]> = {};
    for (const r of risks) {
      const lik = r.likelihood_score ?? scoreFromLabel(r.likelihood);
      const sev = r.severity_score ?? scoreFromLabel(r.severity);
      const key = `${lik}_${sev}`;
      if (!acc[key]) acc[key] = [];
      acc[key].push(r);
    }
    return acc;
  }, [risks]);

  const inherentGrouped = useMemo(() => {
    if (!inherentRisks?.length) return {};
    const acc: Record<string, DsfaRisk[]> = {};
    for (const r of inherentRisks) {
      const lik = r.likelihood_score ?? scoreFromLabel(r.likelihood);
      const sev = r.severity_score ?? scoreFromLabel(r.severity);
      const key = `${lik}_${sev}`;
      if (!acc[key]) acc[key] = [];
      acc[key].push(r);
    }
    return acc;
  }, [inherentRisks]);

  return (
    <div className="space-y-3">
      <div className="text-xs text-muted-foreground">
        Risikomatrix nach ISO 27005 (Likelihood × Severity). Klicke auf eine Zelle, um die zugeordneten
        Risiken zu sehen.
      </div>
      <div className="inline-block">
        {/* Top axis: severity labels */}
        <div className="grid" style={{ gridTemplateColumns: "120px repeat(5, 1fr)" }}>
          <div></div>
          {[1, 2, 3, 4, 5].map((s) => (
            <div key={`sev-h-${s}`} className="text-xs text-center text-muted-foreground px-2 py-1">
              {s}
              <div className="text-[10px] leading-tight">{sevLabels[s]}</div>
            </div>
          ))}
        </div>
        {/* Rows: likelihood from 5 (top) to 1 (bottom) so that highest risk sits top-right */}
        {[5, 4, 3, 2, 1].map((lik) => (
          <div key={`row-${lik}`} className="grid" style={{ gridTemplateColumns: "120px repeat(5, 1fr)" }}>
            <div className="text-xs text-right pr-3 py-3 text-muted-foreground">
              {lik}: <span className="text-foreground">{likLabels[lik]}</span>
            </div>
            {[1, 2, 3, 4, 5].map((sev) => {
              const key = `${lik}_${sev}`;
              const level = cellMap[key] ?? "low";
              const items = grouped[key] ?? [];
              const inherentItems = inherentGrouped[key] ?? [];
              const colour = LEVEL_BG[level] ?? "";
              const tooltipLines: string[] = [];
              if (items.length) {
                tooltipLines.push(...items.map((r) => `• ${r.description}`));
              }
              if (inherentItems.length) {
                tooltipLines.push(
                  ...inherentItems.map((r) => `▢ inherent: ${r.description}`),
                );
              }
              return (
                <div
                  key={key}
                  className={`relative m-0.5 rounded border border-border min-h-[56px] flex items-center justify-center text-sm font-medium ${colour}`}
                  title={
                    tooltipLines.length
                      ? tooltipLines.join("\n")
                      : `${level.toUpperCase()} (${lik}/${sev}) — keine Risiken`
                  }
                >
                  {items.length > 0 ? items.length : ""}
                  {inherentItems.length > 0 && (
                    <span
                      className="absolute top-1 right-1 text-[10px] px-1 rounded border border-dashed border-current opacity-70"
                      aria-label={`${inherentItems.length} inherent (vor Mitigation)`}
                    >
                      ▢{inherentItems.length}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        {["low", "medium", "high", "critical"].map((lvl) => (
          <div key={lvl} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded ${LEVEL_BG[lvl]}`}>
            <span className="capitalize">{lvl}</span>
          </div>
        ))}
        <div className="text-muted-foreground self-center ml-2">
          Achsen: Y = Likelihood (1-5), X = Severity (1-5)
        </div>
      </div>
    </div>
  );
}

function scoreFromLabel(label: string | undefined): number {
  switch ((label ?? "").toLowerCase()) {
    case "low":
      return 1;
    case "medium":
      return 3;
    case "high":
      return 5;
    case "critical":
      return 5;
    default:
      return 3;
  }
}
