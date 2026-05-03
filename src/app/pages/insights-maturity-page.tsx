import { useEffect, useMemo, useState } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { toast } from "sonner";
import { TrendingUp, TrendingDown, Award } from "lucide-react";
import { fetchMaturityStats, type MaturityStats, type MaturityDeptRow } from "../lib/api/insights";

const SUB_LABELS: Record<keyof MaturityDeptRow["subScores"], string> = {
  vvtScore: "VVT",
  dsfaScore: "DSFA",
  avvScore: "AVV",
  tomScore: "TOM",
  velocityScore: "Velocity",
};

function scoreClass(s: number): string {
  if (s >= 80) return "bg-green-500/20 text-green-700 dark:text-green-300";
  if (s >= 60) return "bg-yellow-500/20 text-yellow-700 dark:text-yellow-300";
  if (s >= 40) return "bg-orange-500/20 text-orange-700 dark:text-orange-300";
  return "bg-red-500/20 text-red-700 dark:text-red-300";
}

const TREND_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#ea580c", "#7c3aed", "#0891b2"];

export function InsightsMaturityPage() {
  const [data, setData] = useState<MaturityStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchMaturityStats()
      .then(setData)
      .catch(() => toast.error("Maturity-Daten konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  const sortedDepts = useMemo(() => {
    if (!data) return [];
    return [...data.departments].sort((a, b) => b.compositeScore - a.compositeScore);
  }, [data]);

  const trendChartData = useMemo(() => {
    if (!data || data.trend.length === 0) return null;
    // Top-5 nach aktuellem Composite-Score.
    const topDepts = sortedDepts.slice(0, 5).map((d) => d.department);
    const byDate: Record<string, Record<string, number>> = {};
    for (const point of data.trend) {
      if (!topDepts.includes(point.department)) continue;
      if (!byDate[point.date]) byDate[point.date] = {};
      byDate[point.date][point.department] = point.compositeScore;
    }
    return {
      data: Object.entries(byDate)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, vals]) => ({ date, ...vals })),
      depts: topDepts,
    };
  }, [data, sortedDepts]);

  return (
    <AppLayout>
      <PageHeader
        title="Compliance-Reife"
        description="Reifegrad pro Abteilung über fünf gewichtete Sub-Scores plus 6-Monats-Trend."
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
          {/* Heatmap-Tabelle */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Award className="size-4" /> Reifegrad nach Abteilung
              </CardTitle>
              <CardDescription>
                Composite-Score 0-100. Sub-Scores gewichtet: VVT {data.weights.vvt * 100}% · DSFA {data.weights.dsfa * 100}% · AVV {data.weights.avv * 100}% · TOM {data.weights.tom * 100}% · Velocity {data.weights.velocity * 100}%
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {sortedDepts.length === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">Keine Abteilungen mit Daten.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b border-border bg-muted/40 text-xs">
                      <tr>
                        <th className="text-left py-2.5 px-3 font-medium text-muted-foreground">Abteilung</th>
                        <th className="text-center py-2.5 px-3 font-medium text-muted-foreground">Composite</th>
                        {Object.entries(SUB_LABELS).map(([key, label]) => (
                          <th key={key} className="text-center py-2.5 px-3 font-medium text-muted-foreground">{label}</th>
                        ))}
                        <th className="text-center py-2.5 px-3 font-medium text-muted-foreground">Δ 3M</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedDepts.map((d) => (
                        <tr key={d.department} className="border-b border-border last:border-0 hover:bg-muted/30">
                          <td className="py-2.5 px-3 font-medium max-w-[180px] truncate" title={d.department}>{d.department}</td>
                          <td className="py-2.5 px-3 text-center">
                            <span className={`inline-block px-2 py-0.5 rounded-full font-semibold ${scoreClass(d.compositeScore)}`}>
                              {d.compositeScore.toFixed(0)}
                            </span>
                          </td>
                          {(Object.keys(SUB_LABELS) as Array<keyof typeof SUB_LABELS>).map((k) => (
                            <td key={k} className="py-2.5 px-3 text-center">
                              <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${scoreClass(d.subScores[k])}`}>
                                {d.subScores[k].toFixed(0)}
                              </span>
                            </td>
                          ))}
                          <td className="py-2.5 px-3 text-center">
                            {d.delta3m == null ? (
                              <span className="text-muted-foreground text-xs">–</span>
                            ) : d.delta3m > 0 ? (
                              <span className="text-green-600 dark:text-green-400 font-medium">+{d.delta3m.toFixed(1)}</span>
                            ) : d.delta3m < 0 ? (
                              <span className="text-red-600 dark:text-red-400 font-medium">{d.delta3m.toFixed(1)}</span>
                            ) : (
                              <span className="text-muted-foreground">0</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Trend */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">6-Monats-Trend (Top-5)</CardTitle>
              <CardDescription>
                {data.hasHistory
                  ? "Composite-Score über die letzten 180 Tage. Snapshots werden täglich um 04:00 Uhr erzeugt."
                  : "Noch keine historischen Snapshots – Trends erscheinen, sobald der tägliche Job mindestens einmal lief."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!trendChartData ? (
                <p className="text-sm text-muted-foreground py-6 text-center">Noch keine Trend-Daten.</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={trendChartData.data} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    {trendChartData.depts.map((dept, idx) => (
                      <Line
                        key={dept}
                        type="monotone"
                        dataKey={dept}
                        stroke={TREND_COLORS[idx % TREND_COLORS.length]}
                        dot={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Improvers/Decliners */}
          {(data.improvers.length > 0 || data.decliners.length > 0) && (
            <div className="grid md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="size-4 text-green-600" /> Stärkste Verbesserungen (90 Tage)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {data.improvers.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Keine signifikanten Verbesserungen.</p>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {data.improvers.map((it) => (
                        <li key={it.department} className="flex items-center justify-between gap-3">
                          <span className="font-medium truncate" title={it.department}>{it.department}</span>
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {it.previous.toFixed(0)} → <strong className="text-green-600">{it.current.toFixed(0)}</strong> (+{it.delta.toFixed(1)})
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingDown className="size-4 text-red-600" /> Größte Verschlechterungen (90 Tage)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {data.decliners.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Keine signifikanten Verschlechterungen.</p>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {data.decliners.map((it) => (
                        <li key={it.department} className="flex items-center justify-between gap-3">
                          <span className="font-medium truncate" title={it.department}>{it.department}</span>
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {it.previous.toFixed(0)} → <strong className="text-red-600">{it.current.toFixed(0)}</strong> ({it.delta.toFixed(1)})
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          <p className="text-xs text-muted-foreground text-right">
            Stand: {new Date(data.generatedAt).toLocaleString("de-DE")}
          </p>
        </div>
      )}
    </AppLayout>
  );
}
