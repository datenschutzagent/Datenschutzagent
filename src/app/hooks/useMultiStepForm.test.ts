import { describe, it, expect } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useMultiStepForm, type CaseFormData } from "./useMultiStepForm";

const INITIAL: CaseFormData = {
  title: "",
  department: "",
  caseType: "",
  language: "de",
  description: "",
  assignee: "DSB Team",
  processingContext: "none",
  specialCategoryData: false,
  internationalTransfer: false,
};

describe("useMultiStepForm", () => {
  describe("initial state", () => {
    it("starts on step 1 with the default form data", () => {
      const { result } = renderHook(() => useMultiStepForm());
      expect(result.current.step).toBe(1);
      expect(result.current.formData).toEqual(INITIAL);
      expect(result.current.canProceedToStep2).toBe(false);
    });
  });

  describe("step transitions", () => {
    it("advances with nextStep and clamps at the last step (3)", () => {
      const { result } = renderHook(() => useMultiStepForm());

      act(() => result.current.nextStep());
      expect(result.current.step).toBe(2);

      act(() => result.current.nextStep());
      expect(result.current.step).toBe(3);

      act(() => result.current.nextStep());
      expect(result.current.step).toBe(3);
    });

    it("goes back with prevStep and clamps at the first step (1)", () => {
      const { result } = renderHook(() => useMultiStepForm());

      act(() => result.current.prevStep());
      expect(result.current.step).toBe(1);

      act(() => {
        result.current.nextStep();
        result.current.nextStep();
      });
      expect(result.current.step).toBe(3);

      act(() => result.current.prevStep());
      expect(result.current.step).toBe(2);

      act(() => result.current.prevStep());
      expect(result.current.step).toBe(1);
    });

    it("does not allow nextStep to skip steps (no goTo, strictly sequential)", () => {
      const { result } = renderHook(() => useMultiStepForm());
      act(() => result.current.nextStep());
      expect(result.current.step).toBe(2);
    });
  });

  describe("form data", () => {
    it("supports functional updates via setFormData", () => {
      const { result } = renderHook(() => useMultiStepForm());

      act(() =>
        result.current.setFormData((prev) => ({ ...prev, title: "Neuer Vorgang", specialCategoryData: true })),
      );

      expect(result.current.formData.title).toBe("Neuer Vorgang");
      expect(result.current.formData.specialCategoryData).toBe(true);
      // Untouched fields keep their defaults
      expect(result.current.formData.assignee).toBe("DSB Team");
    });

    it("supports replacing the whole form data object", () => {
      const { result } = renderHook(() => useMultiStepForm());
      const next: CaseFormData = { ...INITIAL, title: "T", department: "IT", language: "en" };

      act(() => result.current.setFormData(next));

      expect(result.current.formData).toEqual(next);
    });
  });

  describe("validation", () => {
    it("canProceedToStep2 requires both title and department", () => {
      const { result } = renderHook(() => useMultiStepForm());

      act(() => result.current.setFormData((p) => ({ ...p, title: "Nur Titel" })));
      expect(result.current.canProceedToStep2).toBe(false);

      act(() => result.current.setFormData((p) => ({ ...p, title: "", department: "IT" })));
      expect(result.current.canProceedToStep2).toBe(false);

      act(() => result.current.setFormData((p) => ({ ...p, title: "Titel", department: "IT" })));
      expect(result.current.canProceedToStep2).toBe(true);
    });

    it("canSubmit requires step-2 preconditions and a selected playbook", () => {
      const { result } = renderHook(() => useMultiStepForm());

      // Nothing filled in yet
      expect(result.current.canSubmit("pb-1")).toBe(false);

      act(() => result.current.setFormData((p) => ({ ...p, title: "Titel", department: "IT" })));
      expect(result.current.canSubmit("")).toBe(false);
      expect(result.current.canSubmit("pb-1")).toBe(true);
    });
  });

  describe("reset", () => {
    it("returns to step 1 and restores the initial form data", () => {
      const { result } = renderHook(() => useMultiStepForm());

      act(() => {
        result.current.setFormData((p) => ({ ...p, title: "X", department: "HR", internationalTransfer: true }));
        result.current.nextStep();
        result.current.nextStep();
      });
      expect(result.current.step).toBe(3);
      expect(result.current.canProceedToStep2).toBe(true);

      act(() => result.current.reset());

      expect(result.current.step).toBe(1);
      expect(result.current.formData).toEqual(INITIAL);
      expect(result.current.canProceedToStep2).toBe(false);
    });
  });
});
