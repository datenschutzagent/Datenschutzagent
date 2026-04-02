import { Link, useLocation } from "react-router";
import { useState } from "react";
import { AppHeaderUser } from "./app-header-user";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";
import { Button } from "./ui/button";
import { useAuthOptional } from "../contexts/AuthContext";
import { useAppConfig } from "../contexts/AppConfigContext";
import { isAdmin } from "../lib/api";
import { Menu } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Vorgänge" },
  { to: "/compliance", label: "Compliance" },
  { to: "/vvt-overview", label: "VVT-Übersicht" },
  { to: "/playbooks", label: "Playbooks" },
  { to: "/legal-bases", label: "Rechtsgrundlagen" },
  { to: "/profile", label: "Mein Profil" },
  { to: "/admin", label: "Verwaltung", adminOnly: true },
];

function isActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(to + "/");
}

interface AppLayoutProps {
  children: React.ReactNode;
  maxWidth?: string;
}

export function AppLayout({ children, maxWidth = "max-w-7xl" }: AppLayoutProps) {
  const location = useLocation();
  const auth = useAuthOptional();
  const appConfig = useAppConfig();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const subtitle = appConfig.org_name || "Datenschutz-Compliance";

  const visibleNavItems = NAV_ITEMS.filter(
    (item) => !item.adminOnly || isAdmin(auth?.user ?? null)
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors">
      {/* Skip Navigation */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md"
      >
        Zum Hauptinhalt springen
      </a>

      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
                Datenschutz-Agent
              </h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                {subtitle}
              </p>
            </div>

            {/* Desktop Navigation */}
            <nav className="hidden lg:flex items-center gap-6">
              {visibleNavItems.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={
                    isActive(location.pathname, item.to)
                      ? "text-sm font-medium text-blue-600 dark:text-blue-400"
                      : "text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
                  }
                  aria-current={isActive(location.pathname, item.to) ? "page" : undefined}
                >
                  {item.label}
                </Link>
              ))}
              <AppHeaderUser />
            </nav>

            {/* Mobile Menu Button */}
            <div className="flex items-center gap-2 lg:hidden">
              <AppHeaderUser />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Navigation öffnen"
              >
                <Menu className="size-5" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Navigation Sheet */}
      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetContent side="left">
          <SheetHeader>
            <SheetTitle>Navigation</SheetTitle>
          </SheetHeader>
          <nav className="flex flex-col gap-1 mt-4">
            {visibleNavItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive(location.pathname, item.to)
                    ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
                }`}
                aria-current={isActive(location.pathname, item.to) ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </SheetContent>
      </Sheet>

      {/* Main Content */}
      <main id="main-content" className={`${maxWidth} mx-auto px-4 sm:px-6 lg:px-8 py-8`}>
        {children}
      </main>
    </div>
  );
}
