import { RouterProvider } from "react-router";
import { AuthProvider } from "./contexts/AuthContext";
import { PreferencesProvider } from "./contexts/PreferencesContext";
import { AppConfigProvider } from "./contexts/AppConfigContext";
import { RunningChecksProvider } from "./contexts/RunningChecksContext";
import { Toaster } from "./components/ui/sonner";
import { router } from "./routes";

export default function App() {
  return (
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
  );
}
