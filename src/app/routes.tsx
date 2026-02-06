import { createBrowserRouter } from "react-router";
import { CasesPage } from "./pages/cases-page";
import { CaseDetailPage } from "./pages/case-detail-page";
import { PlaybooksPage } from "./pages/playbooks-page";
import { PlaybookDetailPage } from "./pages/playbook-detail-page";
import { ProfilePage } from "./pages/profile-page";
import { AdminPage } from "./pages/admin-page";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: CasesPage,
  },
  {
    path: "/cases/:caseId",
    Component: CaseDetailPage,
  },
  {
    path: "/playbooks",
    Component: PlaybooksPage,
  },
  {
    path: "/playbooks/:playbookId",
    Component: PlaybookDetailPage,
  },
  {
    path: "/profile",
    Component: ProfilePage,
  },
  {
    path: "/admin",
    Component: AdminPage,
  },
]);
