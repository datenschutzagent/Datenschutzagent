import { createBrowserRouter, Navigate, useLocation } from "react-router";
import { CasesPage } from "./pages/cases-page";
import { CaseDetailPage } from "./pages/case-detail-page";
import { VvtOverviewPage } from "./pages/vvt-overview-page";
import { ComplianceOverviewPage } from "./pages/compliance-overview-page";
import { PlaybooksPage } from "./pages/playbooks-page";
import { PlaybookDetailPage } from "./pages/playbook-detail-page";
import { LegalBasesPage } from "./pages/legal-bases-page";
import { ProfilePage } from "./pages/profile-page";
import { AdminPage } from "./pages/admin-page";
import { AuthCallbackPage } from "./pages/auth-callback-page";
import { DataBreachesPage } from "./pages/data-breaches-page";
import { AVVPage } from "./pages/avv-page";
import { TOMPage } from "./pages/tom-page";
import { PrivacyPolicyPage } from "./pages/privacy-policy-page";
import { DSRPage } from "./pages/dsr-page";
import { RiskDashboardPage } from "./pages/risk-dashboard-page";
import { InsightsPipelinePage } from "./pages/insights-pipeline-page";
import { InsightsVelocityPage } from "./pages/insights-velocity-page";
import { InsightsMaturityPage } from "./pages/insights-maturity-page";
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
    path: "/vvt-overview",
    element: (
      <AuthGuard>
        <VvtOverviewPage />
      </AuthGuard>
    ),
  },
  {
    path: "/compliance",
    element: (
      <AuthGuard>
        <ComplianceOverviewPage />
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
    path: "/legal-bases",
    element: (
      <AuthGuard>
        <LegalBasesPage />
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
  {
    path: "/data-breaches",
    element: (
      <AuthGuard>
        <DataBreachesPage />
      </AuthGuard>
    ),
  },
  {
    path: "/dsr",
    element: (
      <AuthGuard>
        <DSRPage />
      </AuthGuard>
    ),
  },
  {
    path: "/avv",
    element: (
      <AuthGuard>
        <AVVPage />
      </AuthGuard>
    ),
  },
  {
    path: "/tom",
    element: (
      <AuthGuard>
        <TOMPage />
      </AuthGuard>
    ),
  },
  {
    path: "/privacy-policy",
    element: (
      <AuthGuard>
        <PrivacyPolicyPage />
      </AuthGuard>
    ),
  },
  {
    path: "/risk-dashboard",
    element: (
      <AuthGuard>
        <RiskDashboardPage />
      </AuthGuard>
    ),
  },
  {
    path: "/insights/pipeline",
    element: (
      <AuthGuard>
        <InsightsPipelinePage />
      </AuthGuard>
    ),
  },
  {
    path: "/insights/velocity",
    element: (
      <AuthGuard>
        <InsightsVelocityPage />
      </AuthGuard>
    ),
  },
  {
    path: "/insights/maturity",
    element: (
      <AuthGuard>
        <InsightsMaturityPage />
      </AuthGuard>
    ),
  },
]);
