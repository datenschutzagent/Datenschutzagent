import { useState, useEffect } from "react";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Skeleton } from "../ui/skeleton";
import { Separator } from "../ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../ui/alert-dialog";
import {
  updateDataBreach,
  deleteDataBreach,
  generateBreachNotification,
  getDataBreachActivity,
  type ApiDataBreach,
  type ApiDataBreachActivity,
} from "../../lib/api";
import { toast } from "sonner";
import { AlertTriangle, Clock, CheckCircle, ShieldAlert, Loader2, FileText, Trash2, Eye } from "lucide-react";

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

const BREACH_TYPE_LABELS: Record<string, string> = {
  confidentiality: "Vertraulichkeit",
  integrity: "Integrität",
  availability: "Verfügbarkeit",
};

function hoursUntilDeadline(deadline: string): number {
  return (new Date(deadline).getTime() - Date.now()) / 3_600_000;
}

function DeadlineIndicator({ deadline, status }: { deadline: string; status: string }) {
  const hours = hoursUntilDeadline(deadline);
  const notified = ["reported_to_authority", "closed", "no_notification_required"].includes(
    status,
  );
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

interface DataBreachDetailDialogProps {
  breach: ApiDataBreach;
  onClose: () => void;
  onUpdated: (breach: ApiDataBreach) => void;
  onDeleted: (id: string) => void;
}

export function DataBreachDetailDialog({
  breach,
  onClose,
  onUpdated,
  onDeleted,
}: DataBreachDetailDialogProps) {
  const [current, setCurrent] = useState<ApiDataBreach>(breach);
  const [activity, setActivity] = useState<ApiDataBreachActivity[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  useEffect(() => {
    setCurrent(breach);
    setLoadingActivity(true);
    getDataBreachActivity(breach.id)
      .then(setActivity)
      .finally(() => setLoadingActivity(false));
  }, [breach.id]);

  const handleStatusChange = async (newStatus: string) => {
    setUpdatingStatus(true);
    try {
      const updated = await updateDataBreach(current.id, { status: newStatus });
      setCurrent(updated);
      onUpdated(updated);
      toast.success("Status aktualisiert.");
    } catch {
      toast.error("Fehler beim Aktualisieren.");
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleGenerateDraft = async () => {
    setGeneratingDraft(true);
    try {
      const updated = await generateBreachNotification(current.id);
      setCurrent(updated);
      toast.success("Meldungsentwurf generiert.");
    } catch {
      toast.error("Fehler beim Generieren des Entwurfs.");
    } finally {
      setGeneratingDraft(false);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteDataBreach(current.id);
      toast.success("Datenpanne gelöscht.");
      onDeleted(current.id);
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlert className="size-5 text-orange-500" />
            {current.title}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          <div className="flex flex-wrap gap-3 items-center">
            <Badge variant="outline">{STATUS_LABELS[current.status] ?? current.status}</Badge>
            {current.riskLevel && (
              <span
                className={`text-xs px-2 py-1 rounded-full font-medium ${
                  RISK_COLORS[current.riskLevel] ?? ""
                }`}
              >
                Risiko: {RISK_LABELS[current.riskLevel]}
              </span>
            )}
            <DeadlineIndicator
              deadline={current.notificationDeadline}
              status={current.status}
            />
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Art:</span>{" "}
              {BREACH_TYPE_LABELS[current.breachType]}
            </div>
            <div>
              <span className="text-muted-foreground">Entdeckt:</span>{" "}
              {new Date(current.discoveredAt).toLocaleString("de-DE")}
            </div>
            <div>
              <span className="text-muted-foreground">Meldepflicht bis:</span>{" "}
              <span className="font-medium">
                {new Date(current.notificationDeadline).toLocaleString("de-DE")}
              </span>
            </div>
            {current.department && (
              <div>
                <span className="text-muted-foreground">Abteilung:</span> {current.department}
              </div>
            )}
            {current.affectedPersonsCount != null && (
              <div>
                <span className="text-muted-foreground">Betroffene:</span>{" "}
                {current.affectedPersonsCount}
              </div>
            )}
            {current.affectedDataCategories.length > 0 && (
              <div className="col-span-2">
                <span className="text-muted-foreground">Datenkategorien:</span>{" "}
                {current.affectedDataCategories.join(", ")}
              </div>
            )}
          </div>

          {current.description && (
            <div>
              <p className="text-sm font-medium mb-1">Beschreibung</p>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {current.description}
              </p>
            </div>
          )}

          {current.measuresTaken && (
            <div>
              <p className="text-sm font-medium mb-1">Ergriffene Maßnahmen</p>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {current.measuresTaken}
              </p>
            </div>
          )}

          <div>
            <p className="text-sm font-medium mb-2">Status ändern</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(STATUS_LABELS)
                .filter(([v]) => v !== current.status)
                .map(([v, l]) => (
                  <Button
                    key={v}
                    size="sm"
                    variant="outline"
                    disabled={updatingStatus}
                    onClick={() => void handleStatusChange(v)}
                  >
                    {updatingStatus && (
                      <Loader2 className="size-3 mr-1 animate-spin" />
                    )}
                    {l}
                  </Button>
                ))}
            </div>
          </div>

          <Separator />

          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium flex items-center gap-1">
                <FileText className="size-4" /> Behörden-Meldungsentwurf
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void handleGenerateDraft()}
                disabled={generatingDraft}
              >
                {generatingDraft ? (
                  <Loader2 className="size-3 mr-1 animate-spin" />
                ) : (
                  <Eye className="size-3 mr-1" />
                )}
                {current.draftNotification ? "Neu generieren" : "Generieren"}
              </Button>
            </div>
            {current.draftNotification ? (
              <pre className="text-xs bg-slate-50 dark:bg-slate-900 border rounded-md p-3 whitespace-pre-wrap max-h-64 overflow-y-auto">
                {current.draftNotification}
              </pre>
            ) : (
              <p className="text-xs text-muted-foreground italic">
                Noch kein Entwurf generiert.
              </p>
            )}
          </div>

          <Separator />

          <div>
            <p className="text-sm font-medium mb-2">Aktivitätsprotokoll</p>
            {loadingActivity ? (
              <div className="space-y-1">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : activity.length === 0 ? (
              <p className="text-xs text-muted-foreground">Keine Aktivitäten.</p>
            ) : (
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {activity.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 text-xs">
                    <span className="text-muted-foreground shrink-0">
                      {new Date(a.createdAt).toLocaleString("de-DE")}
                    </span>
                    <span className="font-medium">{a.eventType}</span>
                    {Object.keys(a.payload).length > 0 && (
                      <span className="text-muted-foreground truncate">
                        {Object.entries(a.payload)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(", ")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <Trash2 className="size-4 mr-1" /> Löschen
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Datenpanne löschen?</AlertDialogTitle>
                <AlertDialogDescription>
                  Diese Aktion kann nicht rückgängig gemacht werden.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Abbrechen</AlertDialogCancel>
                <AlertDialogAction onClick={() => void handleDelete()}>Löschen</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button variant="outline" onClick={onClose}>
            Schließen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
