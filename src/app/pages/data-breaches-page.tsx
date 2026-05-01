import { useState, useEffect, useCallback, useMemo } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Skeleton } from "../components/ui/skeleton";
import { DataBreachCreateDialog } from "../components/data-breach/DataBreachCreateDialog";
import { DataBreachDetailDialog } from "../components/data-breach/DataBreachDetailDialog";
import {
  listDataBreaches,
  type ApiDataBreach,
} from "../lib/api";
import { toast } from "sonner";
import { AlertTriangle, Plus, Clock, CheckCircle, ShieldAlert } from "lucide-react";

const BREACH_TYPE_LABELS: Record<string, string> = {
  confidentiality: "Vertraulichkeit",
  integrity: "Integrität",
  availability: "Verfügbarkeit",
};

const STATUS_LABELS: Record<string, string> = {
  discovered: "Entdeckt",
  assessed: "Bewertet",
  reported_to_authority: "Behörde gemeldet",
  reported_to_subjects: "Betroffene informiert",
  closed: "Abgeschlossen",
  no_notification_required: "Keine Meldung nötig",
};

const RISK_COLORS: Record<string, string> = {
  low: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

const RISK_LABELS: Record<string, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  critical: "Kritisch",
};

function hoursUntilDeadline(deadline: string): number {
  return (new Date(deadline).getTime() - Date.now()) / 3_600_000;
}

function DeadlineIndicator({ deadline, status }: { deadline: string; status: string }) {
  const hours = hoursUntilDeadline(deadline);
  const notified = ["reported_to_authority", "closed", "no_notification_required"].includes(status);
  if (notified)
    return (
      <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
        <CheckCircle className="size-3" /> Erledigt
      </span>
    );
  if (hours < 0)
    return (
      <span className="text-xs text-red-600 font-semibold flex items-center gap-1">
        <AlertTriangle className="size-3" /> Frist überschritten
      </span>
    );
  if (hours < 12)
    return (
      <span className="text-xs text-red-500 font-semibold flex items-center gap-1">
        <Clock className="size-3" /> {Math.round(hours)}h verbleibend
      </span>
    );
  if (hours < 48)
    return (
      <span className="text-xs text-orange-500 flex items-center gap-1">
        <Clock className="size-3" /> {Math.round(hours)}h verbleibend
      </span>
    );
  return (
    <span className="text-xs text-slate-500 flex items-center gap-1">
      <Clock className="size-3" /> {Math.round(hours)}h verbleibend
    </span>
  );
}

export function DataBreachesPage() {
  const [breaches, setBreaches] = useState<ApiDataBreach[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState<ApiDataBreach | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listDataBreaches({
        status: statusFilter !== "all" ? statusFilter : undefined,
        overdueOnly,
      });
      setBreaches(r.items);
      setTotal(r.total);
    } catch {
      toast.error("Datenpannen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, overdueOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  const overdue = breaches.filter(
    (b) =>
      !["reported_to_authority", "closed", "no_notification_required"].includes(b.status) &&
      hoursUntilDeadline(b.notificationDeadline) < 0,
  ).length;

  const breachAnalytics = useMemo(() => {
    const notified = breaches.filter(
      (b) =>
        ["reported_to_authority", "reported_to_subjects", "closed"].includes(b.status) &&
        b.authorityNotifiedAt != null,
    );
    const onTime = notified.filter(
      (b) =>
        new Date(b.authorityNotifiedAt!).getTime() <=
        new Date(b.notificationDeadline).getTime(),
    );
    const complianceRate =
      notified.length > 0 ? Math.round((onTime.length / notified.length) * 100) : null;

    const notifyTimes = notified.map(
      (b) =>
        (new Date(b.authorityNotifiedAt!).getTime() - new Date(b.discoveredAt).getTime()) /
        3_600_000,
    );
    const avgHours =
      notifyTimes.length > 0
        ? Math.round(notifyTimes.reduce((a, b) => a + b, 0) / notifyTimes.length)
        : null;

    const byType: Record<string, number> = {};
    for (const b of breaches) {
      byType[b.breachType] = (byType[b.breachType] ?? 0) + 1;
    }

    return { complianceRate, avgHours, byType, notifiedCount: notified.length };
  }, [breaches]);

  return (
    <AppLayout>
      <PageHeader
        title="Datenpannen"
        description="Art. 33/34 DSGVO – 72-Stunden-Meldepflicht bei Datenschutzverletzungen"
      />

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">{total}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Gesamt</div>
          </CardContent>
        </Card>
        <Card className={overdue > 0 ? "border-red-300 dark:border-red-700" : ""}>
          <CardContent className="pt-4 pb-3">
            <div className={`text-2xl font-bold ${overdue > 0 ? "text-red-600" : ""}`}>
              {overdue}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Frist überschritten</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">
              {
                breaches.filter((b) => b.status === "discovered" || b.status === "assessed")
                  .length
              }
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Offen</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">
              {breaches.filter((b) => b.status === "closed").length}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Abgeschlossen</div>
          </CardContent>
        </Card>
      </div>

      {/* Analytics */}
      {breaches.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <Card>
            <CardHeader className="pb-1 pt-4 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                72h-Compliance-Rate
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              {breachAnalytics.complianceRate == null ? (
                <div className="text-sm text-muted-foreground">Noch keine gemeldeten Pannen</div>
              ) : (
                <>
                  <div
                    className={`text-2xl font-bold ${
                      breachAnalytics.complianceRate >= 90
                        ? "text-green-600"
                        : breachAnalytics.complianceRate >= 70
                          ? "text-yellow-600"
                          : "text-red-600"
                    }`}
                  >
                    {breachAnalytics.complianceRate}%
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {breachAnalytics.notifiedCount} Meldungen gesamt
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1 pt-4 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Ø Zeit bis Behördenmeldung
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              {breachAnalytics.avgHours == null ? (
                <div className="text-sm text-muted-foreground">Keine Daten</div>
              ) : (
                <>
                  <div
                    className={`text-2xl font-bold ${
                      breachAnalytics.avgHours <= 72 ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {breachAnalytics.avgHours}h
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Frist: 72h</div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1 pt-4 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                Pannenkategorie
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-1.5">
              {Object.entries(BREACH_TYPE_LABELS).map(([key, label]) => {
                const count = breachAnalytics.byType[key] ?? 0;
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={key} className="flex items-center gap-2 text-xs">
                    <span className="w-24 text-muted-foreground">{label}</span>
                    <div className="flex-1 bg-muted rounded-full h-1.5">
                      <div
                        className="bg-primary h-1.5 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-4 text-right font-medium">{count}</span>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Status filtern" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Status</SelectItem>
            {Object.entries(STATUS_LABELS).map(([v, l]) => (
              <SelectItem key={v} value={v}>
                {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(e) => setOverdueOnly(e.target.checked)}
            className="rounded"
          />
          Nur überfällige
        </label>
        <div className="ml-auto">
          <Button onClick={() => setShowNew(true)}>
            <Plus className="size-4 mr-1" /> Datenpanne erfassen
          </Button>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : breaches.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <ShieldAlert className="size-10 mx-auto mb-3 opacity-40" />
            <p>Keine Datenpannen gefunden.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {breaches.map((b) => (
            <Card
              key={b.id}
              className="hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => setSelected(b)}
            >
              <CardContent className="py-4 px-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm truncate">{b.title}</span>
                      {b.riskLevel && (
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            RISK_COLORS[b.riskLevel] ?? ""
                          }`}
                        >
                          {RISK_LABELS[b.riskLevel]}
                        </span>
                      )}
                      <Badge variant="outline" className="text-xs">
                        {STATUS_LABELS[b.status] ?? b.status}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-3">
                      <span>Art: {BREACH_TYPE_LABELS[b.breachType] ?? b.breachType}</span>
                      {b.department && <span>Abteilung: {b.department}</span>}
                      {b.affectedPersonsCount != null && (
                        <span>Betroffene: {b.affectedPersonsCount}</span>
                      )}
                      <span>
                        Entdeckt: {new Date(b.discoveredAt).toLocaleDateString("de-DE")}
                      </span>
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <DeadlineIndicator deadline={b.notificationDeadline} status={b.status} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <DataBreachCreateDialog
        open={showNew}
        onOpenChange={setShowNew}
        onCreated={(breach) => {
          setBreaches((prev) => [breach, ...prev]);
          setTotal((t) => t + 1);
        }}
      />

      {selected && (
        <DataBreachDetailDialog
          breach={selected}
          onClose={() => setSelected(null)}
          onUpdated={(updated) => {
            setBreaches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
            setSelected(updated);
          }}
          onDeleted={(id) => {
            setBreaches((prev) => prev.filter((b) => b.id !== id));
            setTotal((t) => t - 1);
            setSelected(null);
          }}
        />
      )}
    </AppLayout>
  );
}
