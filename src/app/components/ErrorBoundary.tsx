import { Component, type ErrorInfo, type ReactNode } from "react";
import { logger } from "../lib/logger";

interface Props {
  children: ReactNode;
  /** Optional custom fallback UI. Receives the caught error. */
  fallback?: (error: Error) => ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * React Error Boundary.
 *
 * Wraps a subtree and catches any unhandled JS errors during rendering.
 * Renders a minimal fallback instead of crashing the whole page.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomeComponent />
 *   </ErrorBoundary>
 *
 *   <ErrorBoundary fallback={(e) => <p>Custom error: {e.message}</p>}>
 *     <SomeComponent />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    logger.error("React ErrorBoundary caught an error", { componentStack: info.componentStack ?? "" }, error);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (error) {
      if (this.props.fallback) return this.props.fallback(error);
      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="text-sm font-medium text-destructive">
            Dieser Bereich konnte nicht geladen werden.
          </p>
          <p className="text-xs text-muted-foreground">{error.message}</p>
          <button
            className="text-xs underline text-muted-foreground hover:text-foreground"
            onClick={() => this.setState({ error: null })}
          >
            Erneut versuchen
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
