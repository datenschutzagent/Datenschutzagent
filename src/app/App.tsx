import { RouterProvider } from "react-router";
import { PreferencesProvider } from "./contexts/PreferencesContext";
import { router } from "./routes";

export default function App() {
  return (
    <PreferencesProvider>
      <RouterProvider router={router} />
    </PreferencesProvider>
  );
}
