import { Link, useLocation } from "react-router";
import { useState } from "react";
import { AppHeaderUser } from "./app-header-user";
import { GlobalChecksBanner } from "./global-checks-banner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";
import { Button } from "./ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { useAppConfig } from "../contexts/AppConfigContext";
import { Menu, ChevronDown } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
}

interface NavGroup {
  label: string;
  basePath: string;
  items: NavItem[];
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Vorgänge" },
  { to: "/compliance", label: "Compliance" },
  { to: "/data-breaches", label: "Datenpannen" },
  { to: "/dsr", label: "Betroffenenrechte" },
  { to: "/avv", label: "AVV" },
  { to: "/tom", label: "TOMs" },
  { to: "/privacy-policy", label: "Datenschutzerklärung" },
  { to: "/vvt-overview", label: "VVT-Übersicht" },
  { to: "/playbooks", label: "Playbooks" },
  { to: "/legal-bases", label: "Rechtsgrundlagen" },
];

const INSIGHTS_GROUP: NavGroup = {
  label: "Insights",
  basePath: "/insights",
  items: [
    { to: "/risk-dashboard", label: "Risiko-Dashboard" },
    { to: "/insights/pipeline", label: "Lifecycle-Pipeline" },
    { to: "/insights/velocity", label: "Bearbeitungs-Velocity" },
    { to: "/insights/maturity", label: "Compliance-Reife" },
  ],
};

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
  const appConfig = useAppConfig();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const subtitle = appConfig.org_name || "Datenschutz-Compliance";

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
              {NAV_ITEMS.map((item) => (
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
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className={
                      INSIGHTS_GROUP.items.some((it) => isActive(location.pathname, it.to))
                        ? "flex items-center gap-1 text-sm font-medium text-blue-600 dark:text-blue-400"
                        : "flex items-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
                    }
                  >
                    {INSIGHTS_GROUP.label} <ChevronDown className="size-3.5" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-[12rem]">
                  {INSIGHTS_GROUP.items.map((item) => (
                    <DropdownMenuItem key={item.to} asChild>
                      <Link to={item.to} className="cursor-pointer">{item.label}</Link>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
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
            {NAV_ITEMS.map((item) => (
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
            <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-800">
              <p className="px-3 text-xs font-medium uppercase text-slate-400 dark:text-slate-500 mb-1">
                {INSIGHTS_GROUP.label}
              </p>
              {INSIGHTS_GROUP.items.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors block ${
                    isActive(location.pathname, item.to)
                      ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                      : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
                  }`}
                  aria-current={isActive(location.pathname, item.to) ? "page" : undefined}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </nav>
        </SheetContent>
      </Sheet>

      {/* Running checks status banner (only visible when checks are active) */}
      <GlobalChecksBanner />

      {/* Main Content */}
      <main id="main-content" className={`${maxWidth} mx-auto px-4 sm:px-6 lg:px-8 py-8`}>
        {children}
      </main>
    </div>
  );
}
