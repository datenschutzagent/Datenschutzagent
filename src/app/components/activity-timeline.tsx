import { useEffect, useState } from "react";
import { getCaseActivities, type TimelineActivity } from "../lib/api";
import { activityTypeLabels } from "../lib/mock-data";
import { Card, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { 
  FileText, 
  Upload, 
  RefreshCw, 
  ArrowRight, 
  Play, 
  CheckCircle2, 
  MessageSquare, 
  Calendar, 
  User 
} from "lucide-react";

interface ActivityTimelineProps {
  caseId: string;
}

export function ActivityTimeline({ caseId }: ActivityTimelineProps) {
  const [activities, setActivities] = useState<TimelineActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCaseActivities(caseId)
      .then(setActivities)
      .catch((e) => setError(e instanceof Error ? e.message : "Aktivitäten konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [caseId]);

  const getActivityIcon = (type: TimelineActivity["type"]) => {
    const iconClass = "size-4";
    switch (type) {
      case "case_created":
        return <FileText className={iconClass} />;
      case "document_uploaded":
        return <Upload className={iconClass} />;
      case "document_updated":
        return <RefreshCw className={iconClass} />;
      case "status_changed":
        return <ArrowRight className={iconClass} />;
      case "playbook_run":
        return <Play className={iconClass} />;
      case "finding_status_changed":
        return <CheckCircle2 className={iconClass} />;
      case "comment_added":
        return <MessageSquare className={iconClass} />;
      case "deadline_set":
      case "deadline_changed":
        return <Calendar className={iconClass} />;
      case "assigned":
        return <User className={iconClass} />;
      default:
        return <FileText className={iconClass} />;
    }
  };

  const getActivityColor = (type: TimelineActivity["type"]) => {
    switch (type) {
      case "case_created":
        return "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300";
      case "document_uploaded":
      case "document_updated":
        return "bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300";
      case "status_changed":
        return "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300";
      case "playbook_run":
        return "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300";
      case "finding_status_changed":
        return "bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300";
      case "comment_added":
        return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
      case "deadline_set":
      case "deadline_changed":
        return "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300";
      case "assigned":
        return "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/50 dark:text-cyan-300";
      default:
        return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return {
      date: date.toLocaleDateString("de-DE", { 
        day: "2-digit", 
        month: "short", 
        year: "numeric" 
      }),
      time: date.toLocaleTimeString("de-DE", { 
        hour: "2-digit", 
        minute: "2-digit" 
      }),
    };
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-slate-500 dark:text-slate-400">
          Aktivitäten werden geladen…
        </CardContent>
      </Card>
    );
  }
  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-destructive">
          {error}
        </CardContent>
      </Card>
    );
  }
  if (activities.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-slate-500 dark:text-slate-400">
          Keine Aktivitäten vorhanden
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {activities.map((activity, index) => {
        const { date, time } = formatTimestamp(activity.timestamp);
        const isLast = index === activities.length - 1;

        return (
          <div key={activity.id} className="flex gap-4">
            {/* Timeline line */}
            <div className="flex flex-col items-center">
              <div className={`rounded-full p-2 ${getActivityColor(activity.type)}`}>
                {getActivityIcon(activity.type)}
              </div>
              {!isLast && (
                <div className="w-0.5 bg-slate-200 dark:bg-slate-700 flex-1 mt-2" style={{ minHeight: "40px" }} />
              )}
            </div>

            {/* Activity content */}
            <div className="flex-1 pb-6">
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          {activityTypeLabels[activity.type]}
                        </Badge>
                        <span className="text-sm text-slate-600 dark:text-slate-400">
                          von {activity.performedBy}
                        </span>
                      </div>
                      <p className="text-slate-900 dark:text-slate-100">{activity.description}</p>
                    </div>
                    <div className="text-right ml-4">
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{time}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{date}</p>
                    </div>
                  </div>

                  {/* Metadata display */}
                  {activity.metadata && (
                    <div className="mt-3 text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 rounded p-3 space-y-1">
                      {activity.metadata.comment && (
                        <div>
                          <span className="font-medium">Kommentar:</span> {activity.metadata.comment}
                        </div>
                      )}
                      {activity.metadata.oldValue && activity.metadata.newValue && (
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="bg-background">
                            {activity.metadata.oldValue}
                          </Badge>
                          <ArrowRight className="size-3 text-slate-400 dark:text-slate-500" />
                          <Badge variant="outline" className="bg-background">
                            {activity.metadata.newValue}
                          </Badge>
                        </div>
                      )}
                      {activity.metadata.documentName && (
                        <div className="flex items-center gap-2">
                          <FileText className="size-4 text-slate-400 dark:text-slate-500" />
                          <span className="font-mono text-xs">{activity.metadata.documentName}</span>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        );
      })}
    </div>
  );
}
