/**
 * Structured frontend logger for Datenschutzagent.
 *
 * Provides leveled logging (debug, info, warn, error) with consistent
 * formatting. In production builds only `warn` and `error` are emitted.
 * Every log entry includes an ISO timestamp and an optional context object
 * so that log aggregation tools can parse structured fields.
 *
 * Usage:
 *   import { logger } from "./logger";
 *   logger.info("Case loaded", { caseId: "abc" });
 *   logger.error("API request failed", { url, status: 500 }, err);
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: Record<string, unknown>;
  error?: unknown;
}

/** Pluggable sink – replace in tests or to forward to an error-tracking service. */
export type LogSink = (entry: LogEntry) => void;

const IS_DEV =
  typeof import.meta !== "undefined" &&
  (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV === true;

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

/** Minimum level that will be emitted (debug/info only in dev). */
const MIN_LEVEL: LogLevel = IS_DEV ? "debug" : "warn";

function shouldEmit(level: LogLevel): boolean {
  return LEVEL_ORDER[level] >= LEVEL_ORDER[MIN_LEVEL];
}

function consoleSink(entry: LogEntry): void {
  const prefix = `[${entry.timestamp}] [${entry.level.toUpperCase()}]`;
  const msg = `${prefix} ${entry.message}`;
  switch (entry.level) {
    case "debug":
      // eslint-disable-next-line no-console
      console.debug(msg, ...(entry.context ? [entry.context] : []), ...(entry.error ? [entry.error] : []));
      break;
    case "info":
      // eslint-disable-next-line no-console
      console.info(msg, ...(entry.context ? [entry.context] : []), ...(entry.error ? [entry.error] : []));
      break;
    case "warn":
      // eslint-disable-next-line no-console
      console.warn(msg, ...(entry.context ? [entry.context] : []), ...(entry.error ? [entry.error] : []));
      break;
    case "error":
      // eslint-disable-next-line no-console
      console.error(msg, ...(entry.context ? [entry.context] : []), ...(entry.error ? [entry.error] : []));
      break;
  }
}

class Logger {
  private sinks: LogSink[] = [consoleSink];

  /** Register an additional sink (e.g. Sentry, remote endpoint). */
  addSink(sink: LogSink): void {
    this.sinks.push(sink);
  }

  /** Replace all sinks – useful in tests. */
  setSinks(sinks: LogSink[]): void {
    this.sinks = sinks;
  }

  private emit(
    level: LogLevel,
    message: string,
    context?: Record<string, unknown>,
    error?: unknown
  ): void {
    if (!shouldEmit(level)) return;
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      ...(context !== undefined ? { context } : {}),
      ...(error !== undefined ? { error } : {}),
    };
    for (const sink of this.sinks) {
      try {
        sink(entry);
      } catch {
        // Never let a sink crash the application.
      }
    }
  }

  debug(message: string, context?: Record<string, unknown>): void {
    this.emit("debug", message, context);
  }

  info(message: string, context?: Record<string, unknown>): void {
    this.emit("info", message, context);
  }

  warn(message: string, context?: Record<string, unknown>, error?: unknown): void {
    this.emit("warn", message, context, error);
  }

  error(message: string, context?: Record<string, unknown>, error?: unknown): void {
    this.emit("error", message, context, error);
  }
}

export const logger = new Logger();
