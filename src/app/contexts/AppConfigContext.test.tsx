import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AppConfigProvider, useAppConfig } from "./AppConfigContext";

// ---------------------------------------------------------------------------
// Mock the API module
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => ({
  getAppConfig: vi.fn(),
}));

import { getAppConfig } from "../lib/api";
const mockGetAppConfig = vi.mocked(getAppConfig);

// ---------------------------------------------------------------------------
// Helper component to read context values
// ---------------------------------------------------------------------------

function ConfigDisplay() {
  const config = useAppConfig();
  return (
    <div>
      <span data-testid="app-name">{config.app_name}</span>
      <span data-testid="org-name">{config.org_name}</span>
      <span data-testid="org-profile">{config.org_profile}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AppConfigProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders children", () => {
    mockGetAppConfig.mockResolvedValue({
      app_name: "Test App",
      org_name: "Test Org",
      org_profile: "default",
      processing_context_options: [],
    });
    render(
      <AppConfigProvider>
        <div data-testid="child">Hello</div>
      </AppConfigProvider>
    );
    expect(screen.getByTestId("child")).toBeTruthy();
  });

  it("provides default config before API resolves", () => {
    // Return a promise that never resolves to freeze state at defaults
    mockGetAppConfig.mockReturnValue(new Promise(() => {}));
    render(
      <AppConfigProvider>
        <ConfigDisplay />
      </AppConfigProvider>
    );
    expect(screen.getByTestId("app-name").textContent).toBe("Datenschutz-Agent");
    expect(screen.getByTestId("org-profile").textContent).toBe("default");
  });

  it("updates config after API call resolves", async () => {
    mockGetAppConfig.mockResolvedValue({
      app_name: "Custom App",
      org_name: "My University",
      org_profile: "university",
      processing_context_options: ["cloud", "on-prem"],
    });
    render(
      <AppConfigProvider>
        <ConfigDisplay />
      </AppConfigProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId("app-name").textContent).toBe("Custom App");
    });
    expect(screen.getByTestId("org-name").textContent).toBe("My University");
    expect(screen.getByTestId("org-profile").textContent).toBe("university");
  });

  it("keeps default config when API call fails", async () => {
    mockGetAppConfig.mockRejectedValue(new Error("Network error"));
    render(
      <AppConfigProvider>
        <ConfigDisplay />
      </AppConfigProvider>
    );
    // Wait a tick for the rejected promise to settle
    await waitFor(() => {
      // Config should remain at defaults
      expect(screen.getByTestId("app-name").textContent).toBe("Datenschutz-Agent");
    });
    expect(screen.getByTestId("org-profile").textContent).toBe("default");
  });
});

describe("useAppConfig", () => {
  it("returns default config when used outside provider (via default context)", () => {
    // useAppConfig returns the context value; the default context is DEFAULT_CONFIG
    function Standalone() {
      const cfg = useAppConfig();
      return <span data-testid="name">{cfg.app_name}</span>;
    }
    render(<Standalone />);
    expect(screen.getByTestId("name").textContent).toBe("Datenschutz-Agent");
  });
});
