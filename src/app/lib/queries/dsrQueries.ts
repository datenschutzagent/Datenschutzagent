import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listDSRRequests,
  createDSRRequest,
  updateDSRRequest,
  deleteDSRRequest,
  generateDSRDraft,
  getDSRActivity,
  type ApiDSRRequest,
  type ApiDSRActivity,
  type DSRRequestCreate,
  type DSRRequestUpdate,
} from "../api";

/** Server-side filters of the DSR list — part of the query key. */
export interface DSRListFilter {
  status?: string;
  requestType?: string;
  overdueOnly?: boolean;
}

export interface DSRListResult {
  items: ApiDSRRequest[];
  total: number;
}

export const dsrKeys = {
  all: ["dsr"] as const,
  lists: () => ["dsr", "list"] as const,
  list: (filter?: DSRListFilter) => ["dsr", "list", filter ?? {}] as const,
  activity: (id: string) => ["dsr", "activity", id] as const,
};

export function useDSRRequests(filter?: DSRListFilter) {
  return useQuery<DSRListResult>({
    queryKey: dsrKeys.list(filter),
    queryFn: () => listDSRRequests(filter ?? {}),
  });
}

export function useDSRActivity(id: string | null) {
  return useQuery<ApiDSRActivity[]>({
    queryKey: dsrKeys.activity(id ?? ""),
    queryFn: () => getDSRActivity(id as string),
    enabled: !!id,
  });
}

export function useCreateDSRRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DSRRequestCreate) => createDSRRequest(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dsrKeys.lists() });
    },
  });
}

export function useUpdateDSRRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: DSRRequestUpdate }) =>
      updateDSRRequest(id, body),
    onSuccess: (_updated, { id }) => {
      void queryClient.invalidateQueries({ queryKey: dsrKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: dsrKeys.activity(id) });
    },
  });
}

export function useDeleteDSRRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDSRRequest(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dsrKeys.lists() });
    },
  });
}

export function useGenerateDSRDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => generateDSRDraft(id),
    onSuccess: (_updated, id) => {
      void queryClient.invalidateQueries({ queryKey: dsrKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: dsrKeys.activity(id) });
    },
  });
}
