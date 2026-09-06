import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import { createBrowserRouter, useLocation } from "react-router";
import { useAuthOptional } from "./contexts/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Every page is its own chunk (React.lazy): the initial bundle carries the shell,
// the router and the cases list; Recharts, the Markdown editor and the admin area
// load on first navigation. Pages export named components, hence the `.then` mapping.
function page<T extends ComponentType>(
  load: () => Promise<Record<string, unknown>>,
  name: string,
): LazyExoticComponent<T> {
  return lazy(async () => {
    const mod = await load();
    return { default: mod[name] as T };
  });
}

const CasesPage = page(() => import("./pages/cases-page"), "CasesPage");
const CaseDetailPage = page(() => import("./pages/case-detail-page"), "CaseDetailPage");
const VvtOverviewPage = page(() => import("./pages/vvt-overview-page"), "VvtOverviewPage");
const ComplianceOverviewPage = page(
  () => import("./pages/compliance-overview-page"),
  "ComplianceOverviewPage",
);
const PlaybooksPage = page(() => import("./pages/playbooks-page"), "PlaybooksPage");
const PlaybookDetailPage = page(() => import("./pages/playbook-detail-page"), "PlaybookDetailPage");
const LegalBasesPage = page(() => import("./pages/legal-bases-page"), "LegalBasesPage");
const ProfilePage = page(() => import("./pages/profile-page"), "ProfilePage");
const AdminPage = page(() => import("./pages/admin-page"), "AdminPage");
const AuthCallbackPage = page(() => import("./pages/auth-callback-page"), "AuthCallbackPage");
const DataBreachesPage = page(() => import("./pages/data-breaches-page"), "DataBreachesPage");
const AVVPage = page(() => import("./pages/avv-page"), "AVVPage");
const TOMPage = page(() => import("./pages/tom-page"), "TOMPage");
const PrivacyPolicyPage = page(() => import("./pages/privacy-policy-page"), "PrivacyPolicyPage");
const DSRPage = page(() => import("./pages/dsr-page"), "DSRPage");
const RiskDashboardPage = page(() => import("./pages/risk-dashboard-page"), "RiskDashboardPage");
const InsightsPipelinePage = page(
  () => import("./pages/insights-pipeline-page"),
  "InsightsPipelinePage",
);
const InsightsVelocityPage = page(
  () => import("./pages/insights-velocity-page"),
  "InsightsVelocityPage",
);
const InsightsMaturityPage = page(
  () => import("./pages/insights-maturity-page"),
  "InsightsMaturityPage",
);

function Centered({ text }: { text: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">{text}</p>
    </div>
  );
}

function AuthGuard({ children }: { children: React.ReactNode }) {
  const auth = useAuthOptional();
  const location = useLocation();
  if (!auth) return <>{children}</>;
  if (auth.loading) {
    return <Centered text="Lade…" />;
  }
  const isCallback = location.pathname === "/auth/callback";
  if (auth.authConfig?.oidc_enabled && !auth.isAuthenticated && !isCallback) {
    auth.login();
    return <Centered text="Weiterleitung zur Anmeldung…" />;
  }
  return <>{children}</>;
}

function RouteErrorFallback({ error }: { error: Error }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="text-sm font-medium text-destructive">Diese Seite konnte nicht angezeigt werden.</p>
      <p className="max-w-xl text-xs text-muted-foreground">{error.message}</p>
      <a className="text-sm underline" href="/">
        Zur Vorgangsübersicht
      </a>
    </div>
  );
}

// One boundary per route: a render error in one page no longer unmounts the whole
// app (the global boundary in App.tsx stays as last resort for the shell itself).
function guarded(Page: ComponentType) {
  return (
    <AuthGuard>
      <ErrorBoundary fallback={(error) => <RouteErrorFallback error={error} />}>
        <Suspense fallback={<Centered text="Lade…" />}>
          <Page />
        </Suspense>
      </ErrorBoundary>
    </AuthGuard>
  );
}

export const router = createBrowserRouter([
  {
    path: "/auth/callback",
    element: (
      <Suspense fallback={<Centered text="Lade…" />}>
        <AuthCallbackPage />
      </Suspense>
    ),
  },
  { path: "/", element: guarded(CasesPage) },
  { path: "/cases/:caseId", element: guarded(CaseDetailPage) },
  { path: "/vvt-overview", element: guarded(VvtOverviewPage) },
  { path: "/compliance", element: guarded(ComplianceOverviewPage) },
  { path: "/playbooks", element: guarded(PlaybooksPage) },
  { path: "/playbooks/:playbookId", element: guarded(PlaybookDetailPage) },
  { path: "/legal-bases", element: guarded(LegalBasesPage) },
  { path: "/profile", element: guarded(ProfilePage) },
  { path: "/admin", element: guarded(AdminPage) },
  { path: "/data-breaches", element: guarded(DataBreachesPage) },
  { path: "/dsr", element: guarded(DSRPage) },
  { path: "/avv", element: guarded(AVVPage) },
  { path: "/tom", element: guarded(TOMPage) },
  { path: "/privacy-policy", element: guarded(PrivacyPolicyPage) },
  { path: "/risk-dashboard", element: guarded(RiskDashboardPage) },
  { path: "/insights/pipeline", element: guarded(InsightsPipelinePage) },
  { path: "/insights/velocity", element: guarded(InsightsVelocityPage) },
  { path: "/insights/maturity", element: guarded(InsightsMaturityPage) },
]);
