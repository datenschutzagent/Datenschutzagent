import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listDataBreaches,
  createDataBreach,
  updateDataBreach,
  deleteDataBreach,
  generateBreachNotification,
  getDataBreachActivity,
  type ApiDataBreach,
  type ApiDataBreachActivity,
  type DataBreachCreate,
  type DataBreachUpdate,
} from "../api";

/** Serverseitige Filter der Datenpannen-Liste (Teil des Query-Keys). */
export interface DataBreachListFilter {
  status?: string;
  overdueOnly?: boolean;
}

export interface DataBreachListResult {
  items: ApiDataBreach[];
  total: number;
}

export const dataBreachKeys = {
  all: ["data-breaches"] as const,
  list: (filter?: DataBreachListFilter) => ["data-breaches", "list", filter ?? {}] as const,
  activity: (id: string) => ["data-breaches", id, "activity"] as const,
};

export function useDataBreaches(filter?: DataBreachListFilter) {
  return useQuery<DataBreachListResult>({
    queryKey: dataBreachKeys.list(filter),
    queryFn: () => listDataBreaches(filter ?? {}),
  });
}

export function useDataBreachActivity(id: string) {
  return useQuery<ApiDataBreachActivity[]>({
    queryKey: dataBreachKeys.activity(id),
    queryFn: () => getDataBreachActivity(id),
    enabled: !!id,
  });
}

export function useCreateDataBreach() {
  const queryClient = useQueryClient();
  return useMutation<ApiDataBreach, Error, DataBreachCreate>({
    mutationFn: (body) => createDataBreach(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dataBreachKeys.all });
    },
  });
}

export function useUpdateDataBreach() {
  const queryClient = useQueryClient();
  return useMutation<ApiDataBreach, Error, { id: string; body: DataBreachUpdate }>({
    mutationFn: ({ id, body }) => updateDataBreach(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dataBreachKeys.all });
    },
  });
}

export function useDeleteDataBreach() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => deleteDataBreach(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dataBreachKeys.all });
    },
  });
}

/** LLM-Meldungsentwurf (POST) – liefert die aktualisierte Datenpanne zurück. */
export function useGenerateBreachNotification() {
  const queryClient = useQueryClient();
  return useMutation<ApiDataBreach, Error, string>({
    mutationFn: (id) => generateBreachNotification(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dataBreachKeys.all });
    },
  });
}
