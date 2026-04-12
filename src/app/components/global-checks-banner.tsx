/**
 * Global status banner that shows progress of running playbook checks.
 *
 * Rendered between <header> and <main> in AppLayout.
 * Only mounts DOM when there are tracked jobs — zero visual footprint when idle.
 */
import { Link } from "react-router";
import { useRunningChecks } from "../contexts/RunningChecksContext";
import { Loader2, CheckCircle2, CircleAlert, X } from "lucide-react";

export function GlobalChecksBanner() {
  const { jobs, dismissJob } = useRunningChecks();

  if (jobs.length === 0) return null;

  return (
    <div className="bg-blue-50 dark:bg-blue-950 border-b border-blue-200 dark:border-blue-800 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 space-y-1.5">
        {jobs.map((job) => (
          <JobRow key={job.caseId} job={job} onDismiss={() => dismissJob(job.caseId)} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

interface JobRowProps {
  job: {
    caseId: string;
    caseTitle: string;
    playbookName: string | null;
    status: string;
    checksDone: number;
    checksTotal: number;
  };
  onDismiss: () => void;
}

function JobRow({ job, onDismiss }: JobRowProps) {
  const isRunning = job.status === "running";
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed";

  const pct =
    job.checksTotal > 0
      ? Math.min(100, Math.round((job.checksDone / job.checksTotal) * 100))
      : 0;

  return (
    <div className="flex items-center gap-3 text-sm min-h-[28px]">
      {/* Status icon */}
      {isRunning && <Loader2 className="size-4 text-blue-600 dark:text-blue-400 animate-spin shrink-0" />}
      {isCompleted && <CheckCircle2 className="size-4 text-green-600 dark:text-green-400 shrink-0" />}
      {isFailed && <CircleAlert className="size-4 text-red-600 dark:text-red-400 shrink-0" />}

      {/* Case title link */}
      <Link
        to={`/cases/${job.caseId}`}
        className="font-medium text-blue-700 dark:text-blue-300 hover:underline truncate max-w-[200px] sm:max-w-[300px]"
      >
        {job.caseTitle}
      </Link>

      {/* Playbook name */}
      {job.playbookName && (
        <span className="text-blue-600/70 dark:text-blue-400/70 hidden sm:inline truncate max-w-[200px]">
          — {job.playbookName}
        </span>
      )}

      {/* Progress */}
      {isRunning && job.checksTotal > 0 && (
        <>
          {/* Progress bar (hidden on mobile) */}
          <div className="hidden sm:block flex-1 max-w-[180px] bg-blue-200 dark:bg-blue-800 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-blue-600 dark:bg-blue-400 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>

          {/* Fraction + percent */}
          <span className="text-blue-600 dark:text-blue-400 tabular-nums whitespace-nowrap shrink-0">
            {job.checksDone}/{job.checksTotal}
            <span className="ml-1 text-blue-500/60 dark:text-blue-400/60">({pct}%)</span>
          </span>
        </>
      )}

      {isRunning && job.checksTotal === 0 && (
        <span className="text-blue-600/70 dark:text-blue-400/70">
          Prüfungen werden vorbereitet…
        </span>
      )}

      {isCompleted && (
        <span className="text-green-600 dark:text-green-400">Abgeschlossen</span>
      )}

      {isFailed && (
        <span className="text-red-600 dark:text-red-400">Fehlgeschlagen</span>
      )}

      {/* Dismiss button (only for completed/failed) */}
      {!isRunning && (
        <button
          onClick={(e) => {
            e.preventDefault();
            onDismiss();
          }}
          className="ml-auto p-0.5 rounded hover:bg-blue-200 dark:hover:bg-blue-800 text-blue-500 dark:text-blue-400 shrink-0"
          aria-label="Schließen"
        >
          <X className="size-3.5" />
        </button>
      )}
    </div>
  );
}
