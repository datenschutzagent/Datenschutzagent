import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listAVVContracts,
  createAVVContract,
  updateAVVContract,
  deleteAVVContract,
  assessAvvRisk,
  type ApiAVVContract,
  type AVVCreate,
  type AVVUpdate,
  type AvvRiskAssessment,
} from "../api";

/** Serverseitige Filter der AVV-Liste (Teil des Query-Keys). */
export interface AVVListFilter {
  status?: string;
  expiringSoon?: boolean;
}

export interface AVVListResult {
  items: ApiAVVContract[];
  total: number;
}

export const avvKeys = {
  all: ["avv"] as const,
  list: (filter?: AVVListFilter) => ["avv", "list", filter ?? {}] as const,
};

export function useAVVContracts(filter?: AVVListFilter) {
  return useQuery<AVVListResult>({
    queryKey: avvKeys.list(filter),
    queryFn: () => listAVVContracts(filter ?? {}),
  });
}

export function useCreateAVVContract() {
  const queryClient = useQueryClient();
  return useMutation<ApiAVVContract, Error, AVVCreate>({
    mutationFn: (body) => createAVVContract(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: avvKeys.all });
    },
  });
}

export function useUpdateAVVContract() {
  const queryClient = useQueryClient();
  return useMutation<ApiAVVContract, Error, { id: string; body: AVVUpdate }>({
    mutationFn: ({ id, body }) => updateAVVContract(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: avvKeys.all });
    },
  });
}

export function useDeleteAVVContract() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => deleteAVVContract(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: avvKeys.all });
    },
  });
}

/** LLM-Risikobewertung (POST) – verändert Risk-Score/-Level des Vertrags. */
export function useAssessAvvRisk() {
  const queryClient = useQueryClient();
  return useMutation<AvvRiskAssessment, Error, string>({
    mutationFn: (contractId) => assessAvvRisk(contractId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: avvKeys.all });
    },
  });
}
