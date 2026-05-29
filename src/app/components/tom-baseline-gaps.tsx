/**
 * TomBaselineGaps — Coverage card that shows mandatory TOMs vs. what's
 * actually implemented in the org. Pulls from /tom-gaps (or
 * /cases/{id}/tom-gaps when a caseId is provided) and renders a small
 * heatmap of requirements grouped by severity.
 */
import { useEffect, useState } from "react";

import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Progress } from "./ui/progress";
import { ApiTomGapResponse, getTomGaps } from "../lib/api/compliance";

type Props = { caseId?: string };

const SEVERITY_LABEL: Record<string, string> = {
  info: "Info",
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  critical: "Kritisch",
};

const SEVERITY_VARIANT: Record<string, "secondary" | "default" | "destructive" | "outline"> = {
  info: "outline",
  low: "secondary",
  medium: "default",
  high: "destructive",
  critical: "destructive",
};

export function TomBaselineGaps({ caseId }: Props) {
  const [data, setData] = useState<ApiTomGapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getTomGaps(caseId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [caseId]);

  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Baseline-Coverage (Art. 32 DSGVO)</CardTitle></CardHeader>
        <CardContent><div className="text-xs text-muted-foreground">Lade…</div></CardContent>
      </Card>
    );
  }
  if (error) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Baseline-Coverage</CardTitle></CardHeader>
        <CardContent><div className="text-xs text-destructive">{error}</div></CardContent>
      </Card>
    );
  }
  if (!data || !data.enabled) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Baseline-Coverage</CardTitle></CardHeader>
        <CardContent><div className="text-xs text-muted-foreground">
          Keine Baseline konfiguriert. Setze die Pflicht-TOMs unter
          {" "}<code className="font-mono">risk_config.yaml → tom_baseline</code>.
        </div></CardContent>
      </Card>
    );
  }

  const gaps = data.requirements.filter((r) => !r.met);
  const met = data.requirements.filter((r) => r.met);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Baseline-Coverage (Art. 32 DSGVO){caseId ? " für diesen Vorgang" : ""}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <Progress value={data.summary.coveragePct} className="flex-1 h-3" />
          <span className="text-sm font-semibold tabular-nums">
            {data.summary.met} / {data.summary.total} ({data.summary.coveragePct}%)
          </span>
        </div>

        {gaps.length > 0 && (
          <div>
            <div className="text-sm font-medium mb-2">Offene Pflicht-Maßnahmen</div>
            <ul className="space-y-2">
              {gaps.map((r) => (
                <li key={r.id} className="rounded border border-destructive/30 p-2 bg-destructive/5">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium">{r.label}</div>
                      {r.description && (
                        <div className="text-xs text-muted-foreground">{r.description}</div>
                      )}
                      <div className="text-[11px] text-muted-foreground mt-1">
                        Kategorie: <span className="font-mono">{r.category}</span>
                      </div>
                    </div>
                    <Badge variant={SEVERITY_VARIANT[r.severity] ?? "default"}>
                      {SEVERITY_LABEL[r.severity] ?? r.severity}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {met.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground">
              Erfüllt: {met.length} TOM{met.length === 1 ? "" : "s"}
            </summary>
            <ul className="mt-2 space-y-1">
              {met.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-2 px-2 py-1 rounded bg-muted/40">
                  <span className="font-medium">{r.label}</span>
                  <span className="text-[10px] text-muted-foreground">
                    {r.matchingToms.slice(0, 2).join(", ")}
                    {r.matchingToms.length > 2 ? "…" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </CardContent>
    </Card>
  );
}
