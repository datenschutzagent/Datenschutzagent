import { useEffect, useState } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Skeleton } from "../components/ui/skeleton";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { toast } from "sonner";
import { AlertTriangle, ClipboardCheck, FileWarning, Calendar } from "lucide-react";
import { fetchPipelineStats, type PipelineStats } from "../lib/api/insights";

const BUCKET_COLORS: Record<string, string> = {
  overdue: "#dc2626",
  "0_30": "#ea580c",
  "31_90": "#ca8a04",
  "91_180": "#2563eb",
  "180_plus": "#16a34a",
  undated: "#6b7280",
};

function riskBadge(level: string | null) {
  if (!level) return <span className="text-muted-foreground text-xs">–</span>;
  const cls =
    level === "critical" ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300" :
    level === "high" ? "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300" :
    level === "medium" ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300" :
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300";
  return <Badge className={`${cls} text-xs`}>{level}</Badge>;
}

export function InsightsPipelinePage() {
  const [data, setData] = useState<PipelineStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchPipelineStats()
      .then(setData)
      .catch(() => toast.error("Pipeline-Daten konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppLayout>
      <PageHeader
        title="Lifecycle-Pipeline"
        description="AVV-Ablaufpipeline, TOM-Reviews und DSFA-Coverage – alles, was ansteht oder fehlt."
      />
      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : !data ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">Keine Daten geladen.</CardContent></Card>
      ) : (
        <div className="space-y-6">
          {/* AVV-Pipeline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Calendar className="size-4" /> AVV-Verträge nach Restlaufzeit
              </CardTitle>
              <CardDescription>
                {data.avv.total} Verträge. Durchschnittliches Risiko-Score je Bucket.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={data.avv.buckets} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" name="Anzahl">
                    {data.avv.buckets.map((b) => (
                      <Cell key={b.bucket} fill={BUCKET_COLORS[b.bucket] ?? "#6b7280"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {data.avv.expiringSoon.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm font-medium mb-2">Nächste Ablauftermine</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b border-border bg-muted/40 text-xs">
                        <tr>
                          <th className="text-left py-2 px-3 font-medium text-muted-foreground">Partner</th>
                          <th className="text-left py-2 px-3 font-medium text-muted-foreground">Abteilung</th>
                          <th className="text-left py-2 px-3 font-medium text-muted-foreground">Ablauf</th>
                          <th className="text-left py-2 px-3 font-medium text-muted-foreground">Tage</th>
                          <th className="text-left py-2 px-3 font-medium text-muted-foreground">Risiko</th>
                          <th className="text-left py-2 px-3 font-medium text-muted-foreground">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.avv.expiringSoon.map((it) => (
                          <tr key={it.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                            <td className="py-2 px-3 font-medium max-w-[260px] truncate" title={it.partnerName}>
                              {it.partnerName}
                            </td>
                            <td className="py-2 px-3 text-muted-foreground">{it.department ?? "–"}</td>
                            <td className="py-2 px-3 text-muted-foreground">{it.expiryDate ?? "–"}</td>
                            <td className={`py-2 px-3 font-mono ${it.daysUntilExpiry != null && it.daysUntilExpiry < 0 ? "text-red-600 font-semibold" : ""}`}>
                              {it.daysUntilExpiry ?? "–"}
                            </td>
                            <td className="py-2 px-3">{riskBadge(it.riskLevel)}</td>
                            <td className="py-2 px-3 text-xs text-muted-foreground">{it.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* TOM-Reviews */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ClipboardCheck className="size-4" /> TOM-Reviews
              </CardTitle>
              <CardDescription>
                {data.tom.overdueTotal} überfällig · {data.tom.upcomingTotal} ≤ 30 Tage · {data.tom.noReviewDateTotal} ohne Review-Datum · Governance: {data.tom.reviewGovernancePct}%
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.tom.byCategory.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4">Keine TOMs erfasst.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b border-border bg-muted/40 text-xs">
                      <tr>
                        <th className="text-left py-2 px-3 font-medium text-muted-foreground">Kategorie</th>
                        <th className="text-right py-2 px-3 font-medium text-muted-foreground">Überfällig</th>
                        <th className="text-right py-2 px-3 font-medium text-muted-foreground">≤ 30 Tage</th>
                        <th className="text-right py-2 px-3 font-medium text-muted-foreground">Gesamt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.tom.byCategory.map((c) => (
                        <tr key={c.category} className="border-b border-border last:border-0 hover:bg-muted/30">
                          <td className="py-2 px-3 font-medium">{c.category}</td>
                          <td className={`py-2 px-3 text-right ${c.overdue > 0 ? "text-red-600 font-semibold" : "text-muted-foreground"}`}>
                            {c.overdue || "–"}
                          </td>
                          <td className={`py-2 px-3 text-right ${c.upcoming > 0 ? "text-yellow-600 font-semibold" : "text-muted-foreground"}`}>
                            {c.upcoming || "–"}
                          </td>
                          <td className="py-2 px-3 text-right">{c.total}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {data.tom.overdueItems.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm font-medium mb-2 flex items-center gap-2">
                    <AlertTriangle className="size-4 text-red-500" />
                    Überfällige Reviews (Top {data.tom.overdueItems.length})
                  </div>
                  <ul className="space-y-1.5 text-sm">
                    {data.tom.overdueItems.map((it) => (
                      <li key={it.id} className="flex items-center justify-between gap-3 px-3 py-1.5 rounded border border-border">
                        <span className="truncate" title={it.title}>{it.title}</span>
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          {it.category} · {it.daysOverdue} Tage überfällig
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          {/* DSFA-Coverage */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FileWarning className="size-4" /> DSFA-Coverage
              </CardTitle>
              <CardDescription>
                Vorgänge mit Art. 9 oder Drittland-Transfer und ihre DSFA-Abdeckung. Coverage: {data.dsfa.coveragePct}%
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <Card className="p-3">
                  <div className="text-xs text-muted-foreground">High-Risk gesamt</div>
                  <div className="text-2xl font-bold">{data.dsfa.highRiskTotal}</div>
                </Card>
                <Card className="p-3 border-green-300 dark:border-green-700">
                  <div className="text-xs text-muted-foreground">Mit finalisierter DSFA</div>
                  <div className="text-2xl font-bold text-green-700 dark:text-green-400">{data.dsfa.withFinalized}</div>
                </Card>
                <Card className="p-3 border-yellow-300 dark:border-yellow-700">
                  <div className="text-xs text-muted-foreground">Nur Entwurf</div>
                  <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-400">{data.dsfa.withDraftOnly}</div>
                </Card>
                <Card className="p-3 border-red-300 dark:border-red-700">
                  <div className="text-xs text-muted-foreground">Ohne DSFA</div>
                  <div className="text-2xl font-bold text-red-700 dark:text-red-400">{data.dsfa.withoutDsfa}</div>
                </Card>
              </div>
              {data.dsfa.missingItems.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b border-border bg-muted/40 text-xs">
                      <tr>
                        <th className="text-left py-2 px-3 font-medium text-muted-foreground">Vorgang</th>
                        <th className="text-left py-2 px-3 font-medium text-muted-foreground">Abteilung</th>
                        <th className="text-left py-2 px-3 font-medium text-muted-foreground">Risiko-Marker</th>
                        <th className="text-left py-2 px-3 font-medium text-muted-foreground">DSFA-Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.dsfa.missingItems.map((it) => (
                        <tr key={it.caseId} className="border-b border-border last:border-0 hover:bg-muted/30">
                          <td className="py-2 px-3 font-medium max-w-[300px] truncate" title={it.title}>
                            <a href={`/cases/${it.caseId}`} className="hover:underline">{it.title}</a>
                          </td>
                          <td className="py-2 px-3 text-muted-foreground">{it.department ?? "–"}</td>
                          <td className="py-2 px-3 text-xs">
                            {it.specialCategoryData && <Badge className="mr-1 bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">Art. 9</Badge>}
                            {it.internationalTransfer && <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">Drittland</Badge>}
                          </td>
                          <td className="py-2 px-3 text-xs">
                            {it.hasDraft
                              ? <span className="text-yellow-700 dark:text-yellow-400">Entwurf</span>
                              : <span className="text-red-700 dark:text-red-400">Fehlt</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-green-600 dark:text-green-400">Alle high-risk Vorgänge haben eine finalisierte DSFA.</p>
              )}
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground text-right">
            Stand: {new Date(data.generatedAt).toLocaleString("de-DE")}
          </p>
        </div>
      )}
    </AppLayout>
  );
}
