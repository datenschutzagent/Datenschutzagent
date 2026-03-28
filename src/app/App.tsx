import { RouterProvider } from "react-router";
import { AuthProvider } from "./contexts/AuthContext";
import { PreferencesProvider } from "./contexts/PreferencesContext";
import { AppConfigProvider } from "./contexts/AppConfigContext";
import { Toaster } from "./components/ui/sonner";
import { router } from "./routes";

export default function App() {
  return (
    <AppConfigProvider>
      <AuthProvider>
        <PreferencesProvider>
          <RouterProvider router={router} />
          <Toaster />
        </PreferencesProvider>
      </AuthProvider>
    </AppConfigProvider>
  );
}
