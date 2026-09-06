import { ApiError } from "./api/core";

const MAX_LEN = 300;

/**
 * Human-readable detail for a caught error, meant for toast descriptions.
 *
 * `ApiError` already carries the backend's `detail` text and HTTP status; plain
 * errors contribute their message; anything else falls back to a generic hint.
 * The text is trimmed so a stack trace or HTML body never floods the UI.
 */
export function errorMessage(err: unknown, fallback = "Unbekannter Fehler."): string {
  let text: string;
  if (err instanceof ApiError) {
    text = err.status > 0 ? `${err.message} (HTTP ${err.status})` : err.message;
  } else if (err instanceof Error && err.message) {
    text = err.message;
  } else if (typeof err === "string" && err) {
    text = err;
  } else {
    text = fallback;
  }
  text = text.trim();
  return text.length > MAX_LEN ? `${text.slice(0, MAX_LEN - 1)}…` : text;
}
