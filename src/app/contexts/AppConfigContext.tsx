/**
 * AppConfig context — loads organisation configuration once on app start.
 * Provides org_name, org_profile, and app_name to the entire component tree.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getAppConfig, type ApiAppConfig } from "../lib/api";

const DEFAULT_CONFIG: ApiAppConfig = {
  app_name: "Datenschutz-Agent",
  org_name: "",
  org_profile: "default",
  processing_context_options: [],
};

const AppConfigContext = createContext<ApiAppConfig>(DEFAULT_CONFIG);

export function AppConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<ApiAppConfig>(DEFAULT_CONFIG);

  useEffect(() => {
    getAppConfig()
      .then(setConfig)
      .catch(() => {
        // Keep defaults on error (backend not yet reachable)
      });
  }, []);

  return (
    <AppConfigContext.Provider value={config}>
      {children}
    </AppConfigContext.Provider>
  );
}

export function useAppConfig(): ApiAppConfig {
  return useContext(AppConfigContext);
}
