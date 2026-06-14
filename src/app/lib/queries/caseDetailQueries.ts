import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getCase,
  getRunChecksStatus,
  getCaseRiskScore,
  getSimilarCases,
  updateCase,
  archiveCase,
  unarchiveCase,
  type ApiCase,
  type CaseUpdateInput,
  type CaseRiskScore,
  type CaseSimilarityResult,
  type RunChecksStatusResponse,
  type FindingStatus,
} from "../api/cases";
import {
  updateFindingStatus,
  bulkUpdateFindingStatus,
  getFindingComments,
  createFindingComment,
  type ApiFindingComment,
} from "../api/findings";
import { casesKeys } from "./casesQueries";

export const caseDetailKeys = {
  all: (caseId: string) => ["case", caseId] as const,
  detail: (caseId: string) => ["case", caseId, "detail"] as const,
  runChecksStatus: (caseId: string) => ["case", caseId, "run-checks-status"] as const,
  riskScore: (caseId: string) => ["case", caseId, "risk-score"] as const,
  similarCases: (caseId: string) => ["case", caseId, "similar"] as const,
  findingComments: (findingId: string) => ["finding", findingId, "comments"] as const,
};

export function useCase(caseId: string) {
  return useQuery<ApiCase>({
    queryKey: caseDetailKeys.detail(caseId),
    queryFn: () => getCase(caseId),
    enabled: !!caseId,
  });
}

export function useRunChecksStatus(caseId: string) {
  return useQuery<RunChecksStatusResponse>({
    queryKey: caseDetailKeys.runChecksStatus(caseId),
    queryFn: () => getRunChecksStatus(caseId),
    enabled: !!caseId,
    staleTime: 0,
  });
}

export function useCaseRiskScore(caseId: string) {
  return useQuery<CaseRiskScore>({
    queryKey: caseDetailKeys.riskScore(caseId),
    queryFn: () => getCaseRiskScore(caseId),
    enabled: !!caseId,
    staleTime: 60_000,
  });
}

export function useSimilarCases(caseId: string) {
  return useQuery<CaseSimilarityResult[]>({
    queryKey: caseDetailKeys.similarCases(caseId),
    queryFn: () => getSimilarCases(caseId),
    enabled: !!caseId,
    staleTime: 120_000,
  });
}

export function useFindingComments(findingId: string | null) {
  return useQuery<ApiFindingComment[]>({
    queryKey: caseDetailKeys.findingComments(findingId ?? ""),
    queryFn: () => getFindingComments(findingId as string),
    enabled: !!findingId,
  });
}

export function useUpdateFindingStatus(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ findingId, status }: { findingId: string; status: FindingStatus }) =>
      updateFindingStatus(findingId, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: caseDetailKeys.detail(caseId) });
    },
  });
}

export function useCreateFindingComment(findingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => createFindingComment(findingId, text),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: caseDetailKeys.findingComments(findingId),
      });
    },
  });
}

export function useBulkUpdateFindingStatus(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ids, status }: { ids: string[]; status: FindingStatus }) =>
      bulkUpdateFindingStatus(ids, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: caseDetailKeys.detail(caseId) });
    },
  });
}

export function useUpdateCase(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CaseUpdateInput) => updateCase(caseId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: caseDetailKeys.detail(caseId) });
    },
  });
}

export function useArchiveCase(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => archiveCase(caseId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: caseDetailKeys.detail(caseId) });
      void queryClient.invalidateQueries({ queryKey: casesKeys.all });
    },
  });
}

export function useUnarchiveCase(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unarchiveCase(caseId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: caseDetailKeys.detail(caseId) });
      void queryClient.invalidateQueries({ queryKey: casesKeys.all });
    },
  });
}
