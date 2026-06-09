import React from "react";
import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import type { ApiPlaybook } from "../lib/api";

const getDepartments = vi.fn();
const getPlaybooks = vi.fn();
const getPlaybooksForSelection = vi.fn();
const listCaseTemplates = vi.fn();
const createCase = vi.fn();
const uploadDocumentsBulk = vi.fn();

vi.mock("../lib/api", () => ({
  getDepartments: (...args: unknown[]) => getDepartments(...args),
  getPlaybooks: (...args: unknown[]) => getPlaybooks(...args),
  getPlaybooksForSelection: (...args: unknown[]) => getPlaybooksForSelection(...args),
  listCaseTemplates: (...args: unknown[]) => listCaseTemplates(...args),
  createCase: (...args: unknown[]) => createCase(...args),
  uploadDocumentsBulk: (...args: unknown[]) => uploadDocumentsBulk(...args),
}));

vi.mock("../contexts/AppConfigContext", () => ({
  useAppConfig: vi.fn(() => ({
    app_name: "Datenschutzagent",
    org_name: "Testorg",
    org_profile: "goethe",
    processing_context_options: [],
  })),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("./ui/select", () => {
  const SelectContext = React.createContext<{
    value: string;
    onValueChange: (value: string) => void;
  } | null>(null);

  return {
    Select: ({
      value,
      onValueChange,
      children,
    }: {
      value: string;
      onValueChange: (value: string) => void;
      children: React.ReactNode;
    }) => (
      <SelectContext.Provider value={{ value, onValueChange }}>
        {children}
      </SelectContext.Provider>
    ),
    SelectTrigger: ({
      children,
      id,
    }: {
      children: React.ReactNode;
      id?: string;
    }) => (
      <button type="button" role="combobox" id={id} aria-controls={`${id}-listbox`}>
        {children}
      </button>
    ),
    SelectValue: ({ placeholder }: { placeholder?: string }) => {
      const ctx = React.useContext(SelectContext);
      return <span>{ctx?.value || placeholder}</span>;
    },
    SelectContent: ({
      children,
      id,
    }: {
      children: React.ReactNode;
      id?: string;
    }) => {
      const triggerId = id?.replace("-listbox", "") ?? "select";
      return (
        <div role="listbox" id={`${triggerId}-listbox`}>
          {children}
        </div>
      );
    },
    SelectItem: ({
      value,
      children,
    }: {
      value: string;
      children: React.ReactNode;
    }) => {
      const ctx = React.useContext(SelectContext);
      return (
        <div
          role="option"
          aria-selected={ctx?.value === value}
          onClick={() => ctx?.onValueChange(value)}
        >
          {children}
        </div>
      );
    },
  };
});

import { NewCaseDialog } from "./new-case-dialog";

function makePlaybook(overrides: Partial<ApiPlaybook> = {}): ApiPlaybook {
  return {
    id: "pb-1",
    name: "Playbook One",
    version: "1.0",
    content: {},
    caseType: "Forschungsvorhaben",
    department: "FB 12 – Informatik und Mathematik",
    isActive: true,
    status: "active",
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
    checks: [{ name: "Check A" }],
    ...overrides,
  };
}

async function goToPlaybookStep(playbooks: ApiPlaybook[]) {
  getPlaybooksForSelection.mockResolvedValue(
    playbooks.map((playbook) => ({ playbook, matchPriority: 10 })),
  );

  renderWithProviders(<NewCaseDialog open onOpenChange={vi.fn()} />);

  await userEvent.type(screen.getByLabelText(/Titel des Vorgangs/i), "Test-Vorgang");

  await userEvent.click(screen.getByRole("combobox", { name: /Organisationseinheit/i }));
  await userEvent.click(
    screen.getByRole("option", { name: "FB 12 – Informatik und Mathematik" }),
  );

  await userEvent.click(screen.getByRole("button", { name: "Weiter" }));

  await waitFor(() => {
    expect(getPlaybooksForSelection).toHaveBeenCalled();
  });
}

describe("NewCaseDialog playbook selection", () => {
  beforeAll(() => {
    Element.prototype.hasPointerCapture =
      Element.prototype.hasPointerCapture ?? (() => false);
    Element.prototype.setPointerCapture =
      Element.prototype.setPointerCapture ?? (() => undefined);
    Element.prototype.releasePointerCapture =
      Element.prototype.releasePointerCapture ?? (() => undefined);
  });

  beforeEach(() => {
    vi.clearAllMocks();
    getDepartments.mockResolvedValue([
      {
        code: "FB 12",
        label: "Informatik und Mathematik",
        type: "fachbereich",
        value: "FB 12 – Informatik und Mathematik",
      },
    ]);
    getPlaybooks.mockResolvedValue([]);
    listCaseTemplates.mockResolvedValue([]);
  });

  it("selects only the clicked playbook when multiple share the same caseType", async () => {
    const pbA = makePlaybook({
      id: "pb-a",
      name: "FB 12 Playbook",
      caseType: "Forschungsvorhaben",
    });
    const pbB = makePlaybook({
      id: "pb-b",
      name: "Global Default",
      caseType: "Forschungsvorhaben",
    });

    await goToPlaybookStep([pbA, pbB]);

    await screen.findByTestId("playbook-option-pb-a");
    await screen.findByTestId("playbook-option-pb-b");

    await userEvent.click(screen.getByText("FB 12 Playbook"));

    expect(screen.getByTestId("playbook-option-pb-a").getAttribute("data-selected")).toBe("true");
    expect(screen.getByTestId("playbook-option-pb-b").getAttribute("data-selected")).toBe("false");
  });

  it("auto-selects when exactly one playbook is available", async () => {
    const only = makePlaybook({ id: "pb-only", name: "Only Playbook" });

    await goToPlaybookStep([only]);

    await waitFor(() => {
      expect(screen.getByTestId("playbook-option-pb-only").getAttribute("data-selected")).toBe("true");
    });
  });
});
