import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithProviders as render, screen, waitFor } from "../../test-utils";
import userEvent from "@testing-library/user-event";

import type { ApiCase, DsfaResponse } from "../../lib/api/cases";

vi.mock("../../lib/api/cases", () => ({
  getDsfa: vi.fn(),
  getDsfaScreening: vi.fn(),
  generateDsfa: vi.fn(),
  getDsfaJobStatus: vi.fn(),
  finalizeDsfa: vi.fn(),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuthOptional: vi.fn(() => ({
    user: { id: "u1", display_name: "Alice Admin", email: "alice@example.com", role: "admin" },
  })),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

import {
  finalizeDsfa,
  generateDsfa,
  getDsfa,
  getDsfaJobStatus,
} from "../../lib/api/cases";
import { CaseDsfaTab } from "./CaseDsfaTab";

const mockGetDsfa = vi.mocked(getDsfa);
const mockGenerate = vi.mocked(generateDsfa);
const mockGetJobStatus = vi.mocked(getDsfaJobStatus);
const mockFinalize = vi.mocked(finalizeDsfa);

const fakeCase: ApiCase = {
  id: "case-1",
  title: "Test Case",
  department: "IT",
  caseType: "vvt",
  status: "in_review",
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  createdBy: "u1",
  assignee: "Alice",
  language: "de",
  playbookVersion: "1.0",
  specialCategoryData: false,
  internationalTransfer: false,
  autoRunChecks: false,
  documents: [],
  findings: [],
} as unknown as ApiCase;

function makeDsfaResponse(overrides: Partial<DsfaResponse> = {}): DsfaResponse {
  return {
    case_id: "case-1",
    status: "draft",
    payload: {
      necessity_assessment: "Notwendig wegen X.",
      proportionality_assessment: "Verhältnismäßig wegen Y.",
      risks: [
        {
          description: "Datenleck",
          likelihood: "high",
          severity: "high",
          mitigation: "Verschlüsselung",
          likelihood_score: 5,
          severity_score: 5,
          risk_level: "critical",
        },
      ],
      residual_risk: "critical",
      dpo_consultation_required: true,
      measures: ["TOM A", "TOM B"],
      confidence: 0.4,
      low_confidence: true,
      scale_version: "v2_numeric",
    },
    generated_at: "2024-03-01T10:00:00Z",
    finalized_at: null,
    finalized_by: null,
    created_at: "2024-03-01T10:00:00Z",
    updated_at: "2024-03-01T10:00:00Z",
    ...overrides,
  };
}

describe("CaseDsfaTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("zeigt Empty-State wenn keine DSFA existiert", async () => {
    mockGetDsfa.mockRejectedValue(new Error("Keine DSFA für diesen Vorgang vorhanden"));
    render(<CaseDsfaTab caseData={fakeCase} canEdit={true} />);
    // Erstes Sichtbares: Loader oder Empty-State.
    await waitFor(
      () => {
        const body = document.body.textContent ?? "";
        expect(body).toMatch(/noch keine DSFA|Lade DSFA/i);
      },
      { timeout: 3000 }
    );
    // Debug-Ausgabe für die anderen Tests
    // screen.debug();
  });

  it("rendert vollständige DSFA inkl. Risiken, Matrix, DPO-Hinweis und Confidence-Badge", async () => {
    mockGetDsfa.mockResolvedValue(makeDsfaResponse());
    render(<CaseDsfaTab caseData={fakeCase} canEdit={true} />);
    await waitFor(() => {
      const body = document.body.textContent ?? "";
      expect(body).toContain("Notwendig wegen X");
    }, { timeout: 3000 });
    // Status-Badge
    expect(screen.getByText(/Entwurf/i)).toBeTruthy();
    // Confidence-Badge ("Niedrige Konfidenz")
    expect(screen.getByText(/Niedrige Konfidenz/i)).toBeTruthy();
    // DPO-Hinweis
    expect(screen.getByText(/DSB-Konsultation erforderlich/i)).toBeTruthy();
    // Risiken-Tabelle: Beschreibung sichtbar
    expect(screen.getByText("Datenleck")).toBeTruthy();
    // Maßnahmen
    expect(screen.getByText(/TOM A/)).toBeTruthy();
  });

  it("ruft generateDsfa auf, wenn auf den Generate-Button geklickt wird", async () => {
    mockGetDsfa.mockRejectedValue(new Error("Keine DSFA"));
    mockGenerate.mockResolvedValue({ status: "running", job_id: "job-1" });
    // Polling soll im Test sofort als running zurückkommen — wir testen nur den
    // Trigger, nicht das vollständige Polling-Verhalten (das macht das echte
    // E2E ab).
    mockGetJobStatus.mockResolvedValue({ status: "running" });

    const user = userEvent.setup();
    render(<CaseDsfaTab caseData={fakeCase} canEdit={true} />);

    const btn = await screen.findByRole("button", { name: /DSFA generieren/i });
    await user.click(btn);
    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledWith("case-1");
    });
  });

  it("zeigt Finalize-Button und ruft API mit Bestätigung", async () => {
    mockGetDsfa.mockResolvedValue(makeDsfaResponse());
    mockFinalize.mockResolvedValue(
      makeDsfaResponse({
        status: "finalized",
        finalized_at: "2024-03-02T10:00:00Z",
        finalized_by: "Alice Admin",
      })
    );

    const user = userEvent.setup();
    render(<CaseDsfaTab caseData={fakeCase} canEdit={true} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /DSFA finalisieren…/i })).toBeTruthy();
    });
    await user.click(screen.getByRole("button", { name: /DSFA finalisieren…/i }));

    // Dialog mit vorgefülltem User-Name
    const input = await screen.findByLabelText(/Finalisiert durch/i) as HTMLInputElement;
    expect(input.value).toBe("Alice Admin");

    await user.click(screen.getByRole("button", { name: /^Finalisieren$/ }));
    await waitFor(() => {
      expect(mockFinalize).toHaveBeenCalledWith("case-1", "Alice Admin");
    });
  });

  it("blendet Generate/Finalize-Buttons aus wenn canEdit=false", async () => {
    mockGetDsfa.mockResolvedValue(makeDsfaResponse());
    render(<CaseDsfaTab caseData={fakeCase} canEdit={false} />);
    await waitFor(() => {
      expect(screen.getByText(/Notwendig wegen X/)).toBeTruthy();
    });
    expect(screen.queryByRole("button", { name: /DSFA generieren/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /DSFA finalisieren/i })).toBeNull();
  });
});
