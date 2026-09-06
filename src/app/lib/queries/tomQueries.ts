import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listTOMs,
  getTOMStats,
  createTOM,
  updateTOM,
  deleteTOM,
  listTOMAttachments,
  uploadTOMAttachment,
  deleteTOMAttachment,
  type ApiTOM,
  type ApiTOMStats,
  type ApiTOMAttachment,
  type TOMCreate,
  type TOMUpdate,
} from "../api";

/** Server-side filters of the TOM list — part of the query key. */
export interface TOMListFilter {
  category?: string;
  implementationStatus?: string;
}

export interface TOMListResult {
  items: ApiTOM[];
  total: number;
}

export const tomKeys = {
  all: ["tom"] as const,
  lists: () => ["tom", "list"] as const,
  list: (filter?: TOMListFilter) => ["tom", "list", filter ?? {}] as const,
  stats: () => ["tom", "stats"] as const,
  attachments: (tomId: string) => ["tom", "attachments", tomId] as const,
};

export function useTOMs(filter?: TOMListFilter) {
  return useQuery<TOMListResult>({
    queryKey: tomKeys.list(filter),
    queryFn: () => listTOMs(filter ?? {}),
  });
}

export function useTOMStats() {
  return useQuery<ApiTOMStats>({
    queryKey: tomKeys.stats(),
    queryFn: () => getTOMStats(),
  });
}

export function useTOMAttachments(tomId: string | null) {
  return useQuery<ApiTOMAttachment[]>({
    queryKey: tomKeys.attachments(tomId ?? ""),
    queryFn: () => listTOMAttachments(tomId as string),
    enabled: !!tomId,
  });
}

/** Catalogue mutations touch both the list and the stats (counts, rate). */
function useInvalidateTOMCatalogue() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: tomKeys.lists() });
    void queryClient.invalidateQueries({ queryKey: tomKeys.stats() });
  };
}

export function useCreateTOM() {
  const invalidate = useInvalidateTOMCatalogue();
  return useMutation({
    mutationFn: (body: TOMCreate) => createTOM(body),
    onSuccess: invalidate,
  });
}

export function useUpdateTOM() {
  const invalidate = useInvalidateTOMCatalogue();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: TOMUpdate }) => updateTOM(id, body),
    onSuccess: invalidate,
  });
}

export function useDeleteTOM() {
  const invalidate = useInvalidateTOMCatalogue();
  return useMutation({
    mutationFn: (id: string) => deleteTOM(id),
    onSuccess: invalidate,
  });
}

export function useUploadTOMAttachment(tomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, uploadedBy }: { file: File; uploadedBy: string }) =>
      uploadTOMAttachment(tomId, file, uploadedBy),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tomKeys.attachments(tomId) });
    },
  });
}

export function useDeleteTOMAttachment(tomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (attachmentId: string) => deleteTOMAttachment(tomId, attachmentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tomKeys.attachments(tomId) });
    },
  });
}
