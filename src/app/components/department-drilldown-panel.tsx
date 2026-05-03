import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "./ui/sheet";
import { Card, CardContent } from "./ui/card";
import { Skeleton } from "./ui/skeleton";
import { toast } from "sonner";
import {
  fetchPipelineStats,
  fetchVelocityStats,
  fetchMaturityStats,
  type PipelineStats,
  type VelocityStats,
  type MaturityStats,
} from "../lib/api/insights";

interface Props {
  department: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DepartmentDrilldownPanel({ department, open, onOpenChange }: Props) {
  const [pipeline, setPipeline] = useState<PipelineStats | null>(null);
  const [velocity, setVelocity] = useState<VelocityStats | null>(null);
  const [maturity, setMaturity] = useState<MaturityStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !department) return;
    setLoading(true);
    setPipeline(null);
    setVelocity(null);
    setMaturity(null);
    Promise.all([
      fetchPipelineStats(department),
      fetchVelocityStats(department),
      fetchMaturityStats(department),
    ])
      .then(([p, v, m]) => {
        setPipeline(p);
        setVelocity(v);
        setMaturity(m);
      })
      .catch(() => toast.error("Drill-Down konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [open, department]);

  const fmt = (n: number | null, suffix = "") => (n == null ? "–" : `${n.toFixed(n < 10 ? 1 : 0)}${suffix}`);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{department ?? "Abteilung"}</SheetTitle>
          <SheetDescription>Insights zu Lifecycle, Velocity und Reifegrad für diese Abteilung.</SheetDescription>
        </SheetHeader>
        <div className="mt-4 space-y-4">
          {loading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <>
              {maturity && maturity.departments.length > 0 && (
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm font-medium mb-2">Compliance-Reife</div>
                    <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center">
                      <div>
                        <div className="text-xs text-muted-foreground">Composite</div>
                        <div className="text-xl font-bold">{maturity.departments[0].compositeScore.toFixed(0)}</div>
                      </div>
                      {Object.entries(maturity.departments[0].subScores).map(([k, v]) => (
                        <div key={k}>
                          <div className="text-xs text-muted-foreground">{k.replace("Score", "")}</div>
                          <div className="text-sm font-semibold">{v.toFixed(0)}</div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              {pipeline && (
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm font-medium mb-2">Pipeline</div>
                    <ul className="space-y-1 text-sm">
                      <li>AVV: <strong>{pipeline.avv.total}</strong> Verträge · {pipeline.avv.expiringSoon.length} bald ablaufend</li>
                      <li>TOM: <strong>{pipeline.tom.overdueTotal}</strong> überfällig · {pipeline.tom.upcomingTotal} ≤ 30 Tage</li>
                      <li>DSFA: <strong>{pipeline.dsfa.coveragePct}%</strong> Coverage · {pipeline.dsfa.withoutDsfa} ohne DSFA</li>
                    </ul>
                  </CardContent>
                </Card>
              )}
              {velocity && (
                <Card>
                  <CardContent className="pt-4">
                    <div className="text-sm font-medium mb-2">Velocity</div>
                    <ul className="space-y-1 text-sm">
                      <li>DSR-Median: <strong>{fmt(velocity.dsr.medianDays, " Tage")}</strong> ({velocity.dsr.sampleSize} Anfragen, SLA {fmt(velocity.dsr.slaCompliancePct, "%")})</li>
                      <li>Datenpannen-Median: <strong>{fmt(velocity.breach.medianHoursToAuthority, " h")}</strong> bis Behörde · 72h-SLA {fmt(velocity.breach.sla72hCompliancePct, "%")}</li>
                      <li>Findings: {velocity.findings.length} Schweregrade ausgewertet</li>
                    </ul>
                  </CardContent>
                </Card>
              )}
              <p className="text-xs text-muted-foreground">
                <a className="underline hover:text-foreground" href={`/insights/pipeline`}>Pipeline-Details</a>
                {" · "}
                <a className="underline hover:text-foreground" href={`/insights/velocity`}>Velocity-Details</a>
                {" · "}
                <a className="underline hover:text-foreground" href={`/insights/maturity`}>Maturity-Details</a>
              </p>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
