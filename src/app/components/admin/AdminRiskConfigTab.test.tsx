import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { AdminRiskConfigResponse, RiskConfig } from "../../lib/api/types/risk-config";

// jsdom kennt keinen ResizeObserver — Radix Slider braucht ihn.
beforeAll(() => {
  if (typeof window !== "undefined" && !("ResizeObserver" in window)) {
    (window as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

vi.mock("../../lib/api/admin", () => ({
  getAdminRiskConfig: vi.fn(),
  updateAdminRiskConfig: vi.fn(),
  reloadAdminRiskConfig: vi.fn(),
  previewAdminRiskConfig: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import {
  getAdminRiskConfig,
  previewAdminRiskConfig,
  reloadAdminRiskConfig,
  updateAdminRiskConfig,
} from "../../lib/api/admin";
import { AdminRiskConfigTab } from "./AdminRiskConfigTab";

const mockGet = vi.mocked(getAdminRiskConfig);
const mockUpdate = vi.mocked(updateAdminRiskConfig);
const mockReload = vi.mocked(reloadAdminRiskConfig);
const mockPreview = vi.mocked(previewAdminRiskConfig);

function makeDefaultMatrix(): Record<string, "low" | "medium" | "high" | "critical"> {
  const m: Record<string, "low" | "medium" | "high" | "critical"> = {};
  for (let l = 1; l <= 5; l++) for (let s = 1; s <= 5; s++) m[`${l}_${s}`] = "low";
  m["5_5"] = "critical";
  return m;
}

function makeConfig(): RiskConfig {
  return {
    version: 1,
    avv: {
      level_thresholds: [
        { max_score: 1.5, level: "low" },
        { max_score: 2.5, level: "medium" },
        { max_score: 3.5, level: "high" },
        { max_score: 5.0, level: "critical" },
      ],
      score_normalization: { score_min: 1, score_max: 5 },
      dimension_weights: {},
      min_confidence: 0,
    },
    dsfa_screening: {
      rules: [],
      required_threshold: 2.0,
      factors: [
        {
          id: "profiling",
          label: "Profiling",
          description: "",
          weight: 1.0,
          keywords_processing_context: ["profil"],
          keywords_title: [],
          case_flag: null,
          findings_severity: [],
        },
      ],
    },
    dsfa_assessment: {
      scale_type: "1-5",
      scale_labels: { likelihood: {}, severity: {} },
      matrix: makeDefaultMatrix(),
      dpo_consultation_required_when_residual_in: ["high", "critical"],
      min_confidence: 0,
    },
    case_score: {
      severity_weights: { critical: 30, high: 15, medium: 5, low: 0, info: 0 },
      max_score: 100,
    },
    maturity: {
      weights: { vvt: 0.2, dsfa: 0.2, avv: 0.2, tom: 0.2, velocity: 0.2 },
      velocity: { optimal_days: 14, worst_days: 60 },
    },
    risk_velocity: {
      enabled: true,
      window_days: 90,
      significant_change_pct: 15,
    },
    mitigations: {
      enabled: true,
      min_likelihood: 1,
      min_severity: 1,
      min_avv_score: 1.0,
      catalog: [],
    },
  };
}

function makeResponse(): AdminRiskConfigResponse {
  return {
    config: makeConfig(),
    profile: "default",
    path: "/data/org_profiles/default/risk_config.yaml",
    is_default: false,
  };
}

describe("AdminRiskConfigTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lädt und rendert die Config inkl. Profilpfad", async () => {
    mockGet.mockResolvedValue(makeResponse());
    render(<AdminRiskConfigTab />);
    await waitFor(() => {
      expect(screen.getByText(/Risiko-Konfiguration/)).toBeTruthy();
    });
    // Profil + Pfad rendern
    expect(screen.getByText(/Profil:/)).toBeTruthy();
    const body = document.body.textContent ?? "";
    expect(body).toContain("/data/org_profiles/default/risk_config.yaml");
    expect(screen.getByText(/AVV-Risiko/)).toBeTruthy();
    expect(screen.getByText(/DSFA-Screening/)).toBeTruthy();
    expect(screen.getByText(/Compliance-Reife/)).toBeTruthy();
  });

  it("zeigt rote Warnung, wenn Maturity-Gewichte nicht 1.0 ergeben", async () => {
    const broken = makeResponse();
    broken.config.maturity.weights = { vvt: 0.3, dsfa: 0.3, avv: 0.3, tom: 0.3, velocity: 0.3 };
    mockGet.mockResolvedValue(broken);
    render(<AdminRiskConfigTab />);
    await waitFor(() => {
      expect(screen.getByText(/muss 1\.00 betragen/)).toBeTruthy();
    });
  });

  it("Speichern-Button ist deaktiviert wenn keine Änderungen vorgenommen wurden", async () => {
    mockGet.mockResolvedValue(makeResponse());
    render(<AdminRiskConfigTab />);
    const saveBtn = await screen.findByRole("button", { name: /Speichern$/ });
    expect((saveBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("Reload-Button ruft API und reloadt die Config", async () => {
    mockGet.mockResolvedValue(makeResponse());
    mockReload.mockResolvedValue({ reloaded: true });
    const user = userEvent.setup();
    render(<AdminRiskConfigTab />);
    await screen.findByText(/Risiko-Konfiguration/);
    await user.click(screen.getByRole("button", { name: /Aus Datei neu laden/i }));
    await waitFor(() => {
      expect(mockReload).toHaveBeenCalled();
    });
    // getAdminRiskConfig wird zweimal aufgerufen: einmal auf Mount, einmal nach Reload.
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("Preview-Button öffnet Dialog mit Sample-Daten — nur bei dirty-State", async () => {
    mockGet.mockResolvedValue(makeResponse());
    mockPreview.mockResolvedValue({
      samples: [
        {
          name: "Test-Sample",
          inputs: { x: 1 },
          current: { score: 50 },
          preview: { score: 60 },
        },
      ],
    });
    const user = userEvent.setup();
    render(<AdminRiskConfigTab />);

    const previewBtn = await screen.findByRole("button", { name: /Vorschau \(Dry-Run\)/i });
    // Initial keine Änderungen → Button disabled
    expect((previewBtn as HTMLButtonElement).disabled).toBe(true);

    // Eine Änderung vornehmen: Maturity-Gewicht ändern
    const inputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    // Erste 0.2-Eingabe finden und ändern (Maturity vvt z.B.) — wir nehmen einfach das erste, das den Wert "0.2" hat
    const vvtInput = inputs.find((i) => i.value === "0.2");
    expect(vvtInput).toBeTruthy();
    await user.tripleClick(vvtInput!);
    await user.keyboard("0.25");

    await waitFor(() => {
      expect((previewBtn as HTMLButtonElement).disabled).toBe(false);
    });
    await user.click(previewBtn);
    await waitFor(() => {
      expect(mockPreview).toHaveBeenCalled();
      expect(screen.getByText("Test-Sample")).toBeTruthy();
    });
  });

  it("Speichern öffnet Bestätigungsdialog und ruft updateAdminRiskConfig", async () => {
    mockGet.mockResolvedValue(makeResponse());
    mockUpdate.mockResolvedValue(makeResponse());

    const user = userEvent.setup();
    render(<AdminRiskConfigTab />);
    await screen.findByText(/Risiko-Konfiguration/);

    // Eine kleine Änderung: required_threshold von 2 auf 3
    const thresholdInputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    const target = thresholdInputs.find((i) => i.value === "2");
    expect(target).toBeTruthy();
    await user.tripleClick(target!);
    await user.keyboard("3");

    const saveBtn = await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Speichern$/ }) as HTMLButtonElement;
      expect(btn.disabled).toBe(false);
      return btn;
    });
    await user.click(saveBtn);

    // Bestätigungs-Dialog erscheint
    await waitFor(() => {
      expect(screen.getByText(/wirklich speichern/i)).toBeTruthy();
    });
    // Klick auf Bestätigung
    const confirmBtns = screen.getAllByRole("button", { name: /Speichern$/ });
    await user.click(confirmBtns[confirmBtns.length - 1]);

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalled();
    });
  });
});
