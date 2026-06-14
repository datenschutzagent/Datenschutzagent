import { useState } from "react";

type Language = "de" | "en" | "de_en";

export interface CaseFormData {
  title: string;
  department: string;
  caseType: string;
  language: Language;
  description: string;
  assignee: string;
  processingContext: string;
  specialCategoryData: boolean;
  internationalTransfer: boolean;
}

const INITIAL_FORM_DATA: CaseFormData = {
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

export interface UseMultiStepFormReturn {
  step: 1 | 2 | 3;
  formData: CaseFormData;
  setFormData: React.Dispatch<React.SetStateAction<CaseFormData>>;
  nextStep: () => void;
  prevStep: () => void;
  reset: () => void;
  canProceedToStep2: boolean;
  canSubmit: (selectedPlaybookId: string) => boolean;
}

export function useMultiStepForm(): UseMultiStepFormReturn {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [formData, setFormData] = useState<CaseFormData>(INITIAL_FORM_DATA);

  const canProceedToStep2 = Boolean(formData.title && formData.department);

  return {
    step,
    formData,
    setFormData,
    nextStep: () => setStep((s) => (Math.min(3, s + 1) as 1 | 2 | 3)),
    prevStep: () => setStep((s) => (Math.max(1, s - 1) as 1 | 2 | 3)),
    reset: () => {
      setStep(1);
      setFormData(INITIAL_FORM_DATA);
    },
    canProceedToStep2,
    canSubmit: (selectedPlaybookId: string) => canProceedToStep2 && Boolean(selectedPlaybookId),
  };
}
