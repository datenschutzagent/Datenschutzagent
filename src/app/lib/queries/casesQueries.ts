import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getCases, type ApiCase, type CasesFilter } from "../api/cases";

export const casesKeys = {
  all: ["cases"] as const,
  list: (filter?: CasesFilter) => ["cases", "list", filter ?? {}] as const,
  archived: () => ["cases", "archived"] as const,
};

export function useCases(filter?: CasesFilter) {
  return useQuery<ApiCase[]>({
    queryKey: casesKeys.list(filter),
    queryFn: () => getCases(0, 500, filter),
  });
}

export function useArchivedCases(enabled: boolean) {
  return useQuery<ApiCase[]>({
    queryKey: casesKeys.archived(),
    queryFn: () => getCases(0, 500, {}, true),
    enabled,
  });
}

export function useInvalidateCases() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: casesKeys.all });
}
