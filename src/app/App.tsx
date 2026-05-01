import { RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./contexts/AuthContext";
import { PreferencesProvider } from "./contexts/PreferencesContext";
import { AppConfigProvider } from "./contexts/AppConfigContext";
import { RunningChecksProvider } from "./contexts/RunningChecksContext";
import { Toaster } from "./components/ui/sonner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { router } from "./routes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AppConfigProvider>
          <AuthProvider>
            <PreferencesProvider>
              <RunningChecksProvider>
                <RouterProvider router={router} />
              </RunningChecksProvider>
              <Toaster />
            </PreferencesProvider>
          </AuthProvider>
        </AppConfigProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
