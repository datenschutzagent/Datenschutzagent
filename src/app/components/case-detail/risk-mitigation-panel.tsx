/**
 * RiskMitigationPanel — Inherent vs. Residual risk view with mitigation linking.
 *
 * Works for both DSFA-side (target='case') and AVV-side (target='avv'). The
 * panel:
 *   1. Shows inherent → residual risk-level as two badges with an arrow.
 *   2. Lists active mitigations with their effect, and a remove button.
 *   3. Offers a select to link a new mitigation from the org catalog.
 *
 * Data is fetched via TanStack Query so other views invalidate cleanly
 * after add/remove (e.g. case detail header refreshes its risk score).
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import {
  getCaseRiskDelta,
  getAvvRiskDelta,
  getMitigationCatalog,
  linkCaseMitigation,
  linkAvvMitigation,
  listAvvMitigations,
  listCaseMitigations,
  unlinkAvvMitigation,
  unlinkCaseMitigation,
  type ApiAvvMitigationLink,
  type ApiCaseMitigationLink,
  type ApiMitigationCatalogEntry,
  type ApiRiskDelta,
} from "../../lib/api/compliance";

type Target = { kind: "case"; id: string } | { kind: "avv"; id: string };

type Props = {
  target: Target;
  /** Title override; default: "Mitigation & Restrisiko" */
  title?: string;
};

const LEVEL_BADGE_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  low: "secondary",
  medium: "default",
  high: "destructive",
  critical: "destructive",
};

const LEVEL_LABEL: Record<string, string> = {
  low: "niedrig",
  medium: "mittel",
  high: "hoch",
  critical: "kritisch",
};

export function RiskMitigationPanel({ target, title }: Props) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string>("");

  const linksQuery = useQuery({
    queryKey: ["mitigation-links", target.kind, target.id],
    queryFn: async () => {
      if (target.kind === "case") return listCaseMitigations(target.id);
      return listAvvMitigations(target.id);
    },
  });

  const catalogQuery = useQuery({
    queryKey: ["mitigation-catalog"],
    queryFn: getMitigationCatalog,
    staleTime: 5 * 60 * 1000,
  });

  const deltaQuery = useQuery<ApiRiskDelta | null>({
    queryKey: ["risk-delta", target.kind, target.id],
    queryFn: async () => {
      try {
        if (target.kind === "case") return await getCaseRiskDelta(target.id);
        return await getAvvRiskDelta(target.id);
      } catch {
        // 404 = noch keine Bewertung / DSFA → null statt Error-Boundary.
        return null;
      }
    },
  });

  const linkMutation = useMutation({
    mutationFn: async (mitigationId: string) => {
      if (target.kind === "case") {
        return linkCaseMitigation(target.id, { mitigation_id: mitigationId });
      }
      return linkAvvMitigation(target.id, { mitigation_id: mitigationId });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mitigation-links", target.kind, target.id] });
      qc.invalidateQueries({ queryKey: ["risk-delta", target.kind, target.id] });
      setSelected("");
    },
  });

  const unlinkMutation = useMutation({
    mutationFn: async (mitigationId: string) => {
      if (target.kind === "case") {
        return unlinkCaseMitigation(target.id, mitigationId);
      }
      return unlinkAvvMitigation(target.id, mitigationId);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mitigation-links", target.kind, target.id] });
      qc.invalidateQueries({ queryKey: ["risk-delta", target.kind, target.id] });
    },
  });

  const linkedIds = useMemo(
    () => new Set((linksQuery.data ?? []).map((l) => l.mitigationId)),
    [linksQuery.data],
  );

  const availableForTarget = useMemo(() => {
    const wanted = target.kind === "case" ? "dsfa" : "avv";
    return (catalogQuery.data?.catalog ?? []).filter(
      (m) => (m.appliesTo === wanted || m.appliesTo === "both") && !linkedIds.has(m.id),
    );
  }, [catalogQuery.data, linkedIds, target.kind]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title ?? "Mitigation & Restrisiko"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <RiskDeltaSummary delta={deltaQuery.data ?? null} loading={deltaQuery.isLoading} />

        <div>
          <div className="text-sm font-medium mb-2">Angewendete Maßnahmen</div>
          {linksQuery.isLoading ? (
            <div className="text-xs text-muted-foreground">Lade…</div>
          ) : (linksQuery.data ?? []).length === 0 ? (
            <div className="text-xs text-muted-foreground">
              Noch keine Maßnahmen verknüpft. Wähle unten eine aus dem Katalog, um das Restrisiko zu reduzieren.
            </div>
          ) : (
            <ul className="space-y-2">
              {(linksQuery.data ?? []).map((link) => (
                <MitigationLinkRow
                  key={link.id}
                  link={link}
                  catalogEntry={catalogQuery.data?.catalog.find((m) => m.id === link.mitigationId)}
                  onRemove={() => unlinkMutation.mutate(link.mitigationId)}
                  removing={unlinkMutation.isPending}
                />
              ))}
            </ul>
          )}
        </div>

        <div className="border-t pt-3">
          <div className="text-sm font-medium mb-2">Maßnahme hinzufügen</div>
          <div className="flex gap-2">
            <div className="flex-1">
              <Select value={selected} onValueChange={setSelected}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={
                    catalogQuery.isLoading
                      ? "Lade Katalog…"
                      : availableForTarget.length === 0
                        ? "Keine weiteren Maßnahmen verfügbar"
                        : "Maßnahme aus Katalog wählen"
                  } />
                </SelectTrigger>
                <SelectContent>
                  {availableForTarget.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      <span className="flex flex-col">
                        <span>{m.label}</span>
                        <span className="text-[10px] text-muted-foreground">{m.description}</span>
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => selected && linkMutation.mutate(selected)}
              disabled={!selected || linkMutation.isPending}
            >
              {linkMutation.isPending ? "Speichere…" : "Verknüpfen"}
            </Button>
          </div>
          {linkMutation.isError && (
            <div className="text-xs text-destructive mt-2">
              Verknüpfung fehlgeschlagen. Bitte erneut versuchen.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function RiskDeltaSummary({
  delta,
  loading,
}: {
  delta: ApiRiskDelta | null;
  loading: boolean;
}) {
  if (loading) {
    return <div className="text-xs text-muted-foreground">Lade Risiko-Vergleich…</div>;
  }
  if (!delta) {
    return (
      <div className="text-xs text-muted-foreground">
        Noch keine Bewertung vorhanden. Sobald eine Risikobewertung erstellt wurde, erscheint hier der Vor-/Nach-Vergleich.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] items-center gap-3">
      <RiskSide title="Inherent (vor Mitigation)" level={delta.inherent.riskLevel} score={delta.inherent.riskScore} />
      <div className="text-2xl text-muted-foreground text-center" aria-hidden>
        →
      </div>
      <RiskSide title="Residual (nach Mitigation)" level={delta.residual.riskLevel} score={delta.residual.riskScore} />
    </div>
  );
}

function RiskSide({
  title,
  level,
  score,
}: {
  title: string;
  level: string | null;
  score: number | null;
}) {
  const label = level ? LEVEL_LABEL[level] ?? level : "—";
  return (
    <div className="rounded border p-3 space-y-1">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{title}</div>
      <div className="flex items-baseline gap-2">
        <Badge variant={level ? LEVEL_BADGE_VARIANT[level] ?? "default" : "outline"}>{label}</Badge>
        {score !== null && (
          <span className="text-lg font-semibold tabular-nums">{score}</span>
        )}
        {score !== null && <span className="text-xs text-muted-foreground">/ 100</span>}
      </div>
    </div>
  );
}

function MitigationLinkRow({
  link,
  catalogEntry,
  onRemove,
  removing,
}: {
  link: ApiCaseMitigationLink | ApiAvvMitigationLink;
  catalogEntry: ApiMitigationCatalogEntry | undefined;
  onRemove: () => void;
  removing: boolean;
}) {
  const entry = link.catalogEntry ?? catalogEntry;
  return (
    <li className="flex items-start justify-between gap-3 rounded border p-2">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium">{entry?.label ?? link.mitigationId}</div>
        {entry?.description && (
          <div className="text-xs text-muted-foreground line-clamp-2">{entry.description}</div>
        )}
        {entry && (
          <div className="text-[11px] text-muted-foreground mt-1">
            <ReductionDescription entry={entry} />
          </div>
        )}
      </div>
      <Button variant="outline" size="sm" onClick={onRemove} disabled={removing}>
        Entfernen
      </Button>
    </li>
  );
}

function ReductionDescription({ entry }: { entry: ApiMitigationCatalogEntry }) {
  const parts: string[] = [];
  const r = entry.reduction;
  if (r.scoreDelta) parts.push(`AVV-Score ${r.scoreDelta}`);
  if (r.likelihoodDelta) parts.push(`Likelihood ${r.likelihoodDelta}`);
  if (r.severityDelta) parts.push(`Severity ${r.severityDelta}`);
  for (const [dim, delta] of Object.entries(r.dimensionDeltas)) {
    parts.push(`${dim} ${delta}`);
  }
  if (parts.length === 0) return <span>Keine Risiko-Reduktion hinterlegt.</span>;
  return <span>Reduktion: {parts.join(", ")}</span>;
}
