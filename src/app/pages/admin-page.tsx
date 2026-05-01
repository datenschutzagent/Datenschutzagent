import { useNavigate } from "react-router";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { AdminSystemTab } from "../components/admin/AdminSystemTab";
import { AdminPromptsTab } from "../components/admin/AdminPromptsTab";
import { AdminUsersTab } from "../components/admin/AdminUsersTab";
import { useAuthOptional } from "../contexts/AuthContext";
import { isAdmin } from "../lib/api";
import { CircleAlert } from "lucide-react";

export function AdminPage() {
  const navigate = useNavigate();
  const auth = useAuthOptional();

  if (auth?.user && !isAdmin(auth.user)) {
    return (
      <AppLayout maxWidth="max-w-4xl">
        <Alert className="border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30">
          <CircleAlert className="size-4 text-amber-600 dark:text-amber-400" />
          <AlertDescription className="text-amber-800 dark:text-amber-200">
            Sie haben keine Berechtigung fuer die Verwaltung. Nur Nutzer mit der Rolle
            "Admin" koennen diese Seite aufrufen.
          </AlertDescription>
        </Alert>
        <Button className="mt-4" variant="outline" onClick={() => navigate("/")}>
          Zurück zur Startseite
        </Button>
      </AppLayout>
    );
  }

  return (
    <AppLayout maxWidth="max-w-4xl">
      <PageHeader title="Verwaltung" />
      <AdminSystemTab />
      <AdminPromptsTab />
      <AdminUsersTab />
    </AppLayout>
  );
}
