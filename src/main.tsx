import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import "./styles/index.css";
import { logger } from "./app/lib/logger";

// Global handler for synchronous JS errors not caught by an ErrorBoundary.
window.addEventListener("error", (event) => {
  logger.error("Uncaught global error", {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno,
  }, event.error);
});

// Global handler for unhandled Promise rejections.
window.addEventListener("unhandledrejection", (event) => {
  logger.error("Unhandled Promise rejection", {}, event.reason);
});

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error('Root element "#root" not found in index.html');
}
createRoot(rootElement).render(<App />);
