import { Link } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { AppLayout } from "../components/app-layout";
import { statusLabels, statusColors } from "../lib/mock-data";
import type { CaseStatus } from "../lib/mock-data";
import {
  getVvtOverview,
  getVvtOverviewStats,
  getVvtOverviewExportBlob,
  downloadBlob,
  getDepartments,
  type ApiVVTOverviewItem,
  type ApiVVTOverviewStats,
  type ApiDepartment,
} from "../lib/api";
import { Download, FileText, Loader2, BarChart3 } from "lucide-react";
import { useState, useEffect } from "react";

const CASE_TYPE_OPTIONS = ["Forschungsvorhaben", "Allgemein"];
const HAS_VVT_OPTIONS = [
  { value: "all", label: "Alle" },
  { value: "yes", label: "Nur mit VVT" },
  { value: "no", label: "Nur ohne VVT" },
];

export function VvtOverviewPage() {
  const [items, setItems] = useState<ApiVVTOverviewItem[]>([]);
  const [stats, setStats] = useState<ApiVVTOverviewStats | null>(null);
  const [departments, setDepartments] = useState<ApiDepartment[]>([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [exportLoading, setExportLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [department, setDepartment] = useState<string>("all");
  const [caseType, setCaseType] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [hasVvt, setHasVvt] = useState<string>("all");

  const loadDepartments = async () => {
    try {
      const list = await getDepartments();
      setDepartments(list);
    } catch {
      setDepartments([]);
    }
  };

  const loadOverview = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | boolean | undefined> = {
        skip: 0,
        limit: 500,
      };
      if (department !== "all") params.department = department;
      if (caseType !== "all") params.case_type = caseType;
      if (status !== "all") params.status = status;
      if (hasVvt === "yes") params.has_vvt = true;
      if (hasVvt === "no") params.has_vvt = false;
      const list = await getVvtOverview(params);
      setItems(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler beim Laden");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    setStatsLoading(true);
    try {
      const data = await getVvtOverviewStats();
      setStats(data);
    } catch {
      setStats(null);
    } finally {
      setStatsLoading(false);
    }
  };

  useEffect(() => {
    loadDepartments();
  }, []);

  useEffect(() => {
    loadOverview();
  }, [department, caseType, status, hasVvt]);

  useEffect(() => {
    loadStats();
  }, []);

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const params: Record<string, string | boolean | undefined> = {};
      if (department !== "all") params.department = department;
      if (caseType !== "all") params.case_type = caseType;
      if (status !== "all") params.status = status;
      if (hasVvt === "yes") params.has_vvt = true;
      if (hasVvt === "no") params.has_vvt = false;
      const blob = await getVvtOverviewExportBlob(params, "csv");
      const date = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `VVT-Uebersicht-${date}.csv`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export fehlgeschlagen");
    } finally {
      setExportLoading(false);
    }
  };

  const statusLabel = (s: string) =>
    statusLabels[s as CaseStatus] ?? s;
  const statusColor = (s: string) =>
    statusColors[s as CaseStatus] ?? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";

  return (
    <AppLayout>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-foreground">
              VVT-Übersicht (Universitätsebene)
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Tabellarische Übersicht aller Vorgänge mit VVT-Status und Vollständigkeit
            </p>
          </div>
          <Button
            className="gap-2"
            onClick={handleExport}
            disabled={exportLoading}
          >
            {exportLoading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Als CSV exportieren
          </Button>
        </div>

        {/* Stats */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="size-4" />
              Statistik
            </CardTitle>
            <CardDescription>Kennzahlen und Verteilung nach Fachbereich und Vorgangstyp</CardDescription>
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Lade Statistik…
              </div>
            ) : stats ? (
              <div className="space-y-6">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="rounded-lg border bg-muted/50 p-4">
                    <p className="text-xs text-muted-foreground">Vorgänge gesamt</p>
                    <p className="text-2xl font-semibold">{stats.total_cases}</p>
                  </div>
                  <div className="rounded-lg border bg-muted/50 p-4">
                    <p className="text-xs text-muted-foreground">Mit VVT-Dokument</p>
                    <p className="text-2xl font-semibold text-green-600 dark:text-green-400">
                      {stats.with_vvt}
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/50 p-4">
                    <p className="text-xs text-muted-foreground">Ohne VVT-Dokument</p>
                    <p className="text-2xl font-semibold text-amber-600 dark:text-amber-400">
                      {stats.without_vvt}
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/50 p-4">
                    <p className="text-xs text-muted-foreground">Ø VVT-Vollständigkeit</p>
                    <p className="text-2xl font-semibold">
                      {stats.avg_completeness != null ? `${stats.avg_completeness} %` : "–"}
                    </p>
                  </div>
                </div>
                {stats.by_department.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">Nach Fachbereich</h4>
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Fachbereich</TableHead>
                            <TableHead className="text-right">Gesamt</TableHead>
                            <TableHead className="text-right">Mit VVT</TableHead>
                            <TableHead className="text-right">Ohne VVT</TableHead>
                            <TableHead className="text-right">Ø Vollst.</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {stats.by_department.map((g) => (
                            <TableRow key={g.name}>
                              <TableCell className="font-medium">{g.name}</TableCell>
                              <TableCell className="text-right">{g.total_cases}</TableCell>
                              <TableCell className="text-right">{g.with_vvt}</TableCell>
                              <TableCell className="text-right">{g.without_vvt}</TableCell>
                              <TableCell className="text-right">
                                {g.avg_completeness != null ? `${g.avg_completeness} %` : "–"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                )}
                {stats.by_case_type.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2">Nach Vorgangstyp</h4>
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Vorgangstyp</TableHead>
                            <TableHead className="text-right">Gesamt</TableHead>
                            <TableHead className="text-right">Mit VVT</TableHead>
                            <TableHead className="text-right">Ohne VVT</TableHead>
                            <TableHead className="text-right">Ø Vollst.</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {stats.by_case_type.map((g) => (
                            <TableRow key={g.name}>
                              <TableCell className="font-medium">{g.name}</TableCell>
                              <TableCell className="text-right">{g.total_cases}</TableCell>
                              <TableCell className="text-right">{g.with_vvt}</TableCell>
                              <TableCell className="text-right">{g.without_vvt}</TableCell>
                              <TableCell className="text-right">
                                {g.avg_completeness != null ? `${g.avg_completeness} %` : "–"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Statistik nicht verfügbar.</p>
            )}
          </CardContent>
        </Card>

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Fachbereich</label>
                <Select value={department} onValueChange={setDepartment}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle</SelectItem>
                    {departments.map((d) => (
                      <SelectItem key={d.value} value={d.value}>
                        {d.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Vorgangstyp</label>
                <Select value={caseType} onValueChange={setCaseType}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle</SelectItem>
                    {CASE_TYPE_OPTIONS.map((t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Status</label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Alle</SelectItem>
                    {Object.entries(statusLabels).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">VVT</label>
                <Select value={hasVvt} onValueChange={setHasVvt}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {HAS_VVT_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="size-4" />
              Vorgänge
            </CardTitle>
            <CardDescription>
              {items.length} {items.length === 1 ? "Vorgang" : "Vorgänge"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <div className="rounded-md bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 px-4 py-3 mb-4 text-sm">
                {error}
              </div>
            )}
            {loading ? (
              <div className="flex items-center gap-2 text-muted-foreground py-8">
                <Loader2 className="size-4 animate-spin" />
                Lade Übersicht…
              </div>
            ) : items.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">Keine Vorgänge gefunden.</p>
            ) : (
              <>
                {/* Mobile card view */}
                <div className="md:hidden space-y-3">
                  {items.map((row) => (
                    <Link
                      key={row.case_id}
                      to={`/cases/${row.case_id}`}
                      className="block"
                    >
                      <div className="rounded-lg border p-4 hover:bg-muted/50 transition-colors">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <span className="font-medium text-sm leading-snug">{row.title}</span>
                          <Badge className={statusColor(row.status)} >
                            {statusLabel(row.status)}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          <span>{row.department}</span>
                          <span>{row.case_type}</span>
                          <span>
                            VVT:{" "}
                            {row.has_vvt_document
                              ? row.vvt_completeness != null
                                ? `${row.vvt_completeness} %`
                                : "Ja"
                              : "Nein"}
                          </span>
                          <span>
                            {new Date(row.updated_at).toLocaleDateString("de-DE", {
                              day: "2-digit",
                              month: "2-digit",
                              year: "numeric",
                            })}
                          </span>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>

                {/* Desktop table view */}
                <div className="hidden md:block overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Titel</TableHead>
                        <TableHead>Fachbereich</TableHead>
                        <TableHead>Vorgangstyp</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>VVT vorhanden</TableHead>
                        <TableHead className="text-right">VVT-Vollständigkeit</TableHead>
                        <TableHead>Stand</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {items.map((row) => (
                        <TableRow key={row.case_id} className="hover:bg-muted/50 cursor-pointer transition-colors">
                          <TableCell>
                            <Link
                              to={`/cases/${row.case_id}`}
                              className="font-medium text-blue-600 dark:text-blue-400 hover:underline"
                            >
                              {row.title}
                            </Link>
                          </TableCell>
                          <TableCell>{row.department}</TableCell>
                          <TableCell>{row.case_type}</TableCell>
                          <TableCell>
                            <Badge className={statusColor(row.status)}>
                              {statusLabel(row.status)}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {row.has_vvt_document ? (
                              <Badge className="bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">
                                Ja
                              </Badge>
                            ) : (
                              <Badge variant="secondary">Nein</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {row.vvt_completeness != null ? `${row.vvt_completeness} %` : "–"}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {new Date(row.updated_at).toLocaleDateString("de-DE", {
                              day: "2-digit",
                              month: "2-digit",
                              year: "numeric",
                            })}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </>
            )}
          </CardContent>
        </Card>
    </AppLayout>
  );
}
