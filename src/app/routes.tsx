import { createBrowserRouter, Navigate, useLocation } from "react-router";
import { CasesPage } from "./pages/cases-page";
import { CaseDetailPage } from "./pages/case-detail-page";
import { PlaybooksPage } from "./pages/playbooks-page";
import { PlaybookDetailPage } from "./pages/playbook-detail-page";
import { ProfilePage } from "./pages/profile-page";
import { AdminPage } from "./pages/admin-page";
import { AuthCallbackPage } from "./pages/auth-callback-page";
import { useAuthOptional } from "./contexts/AuthContext";

function AuthGuard({ children }: { children: React.ReactNode }) {
  const auth = useAuthOptional();
  const location = useLocation();
  if (!auth) return <>{children}</>;
  if (auth.loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Lade…</p>
      </div>
    );
  }
  const isCallback = location.pathname === "/auth/callback";
  if (auth.authConfig?.oidc_enabled && !auth.isAuthenticated && !isCallback) {
    auth.login();
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Weiterleitung zur Anmeldung…</p>
      </div>
    );
  }
  return <>{children}</>;
}

export const router = createBrowserRouter([
  {
    path: "/auth/callback",
    Component: AuthCallbackPage,
  },
  {
    path: "/",
    element: (
      <AuthGuard>
        <CasesPage />
      </AuthGuard>
    ),
  },
  {
    path: "/cases/:caseId",
    element: (
      <AuthGuard>
        <CaseDetailPage />
      </AuthGuard>
    ),
  },
  {
    path: "/playbooks",
    element: (
      <AuthGuard>
        <PlaybooksPage />
      </AuthGuard>
    ),
  },
  {
    path: "/playbooks/:playbookId",
    element: (
      <AuthGuard>
        <PlaybookDetailPage />
      </AuthGuard>
    ),
  },
  {
    path: "/profile",
    element: (
      <AuthGuard>
        <ProfilePage />
      </AuthGuard>
    ),
  },
  {
    path: "/admin",
    element: (
      <AuthGuard>
        <AdminPage />
      </AuthGuard>
    ),
  },
]);
