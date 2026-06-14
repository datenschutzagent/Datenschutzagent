import { createContext, useContext } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { AdminRiskConfigResponse, RiskConfig } from "../../lib/api/types/risk-config";

export interface AdminRiskConfigContextValue {
  config: RiskConfig;
  setConfig: Dispatch<SetStateAction<RiskConfig | null>>;
  meta: AdminRiskConfigResponse;
  dirty: boolean;
  maturityValid: boolean;
  thresholdsAscending: boolean;
  velocityValid: boolean;
  scoreRangeValid: boolean;
  canSave: boolean;
}

export const AdminRiskConfigContext = createContext<AdminRiskConfigContextValue | null>(null);

export function useAdminRiskConfig(): AdminRiskConfigContextValue {
  const ctx = useContext(AdminRiskConfigContext);
  if (!ctx) throw new Error("useAdminRiskConfig must be used inside AdminRiskConfigTab");
  return ctx;
}
