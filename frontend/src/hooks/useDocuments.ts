import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { documentService } from "@/services/document.service";
import type { Document } from "@/types/api";

const docKey = (conversationId: string) => ["documents", conversationId] as const;

export function useDocuments(conversationId: string | null) {
  return useQuery({
    queryKey: docKey(conversationId!),
    queryFn: () => documentService.list(conversationId!),
    enabled: !!conversationId,
    // Poll while any doc is pending/indexing (resolves automatically once all ready)
    refetchInterval: (query) => {
      const docs = query.state.data;
      if (!docs) return false;
      const busy = docs.some((d) => d.status === "pending" || d.status === "indexing");
      return busy ? 3000 : false;
    },
    staleTime: 10_000,
  });
}

export function useUploadDocument(conversationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => documentService.upload(conversationId, file),
    onSuccess: (doc) => {
      queryClient.setQueryData<Document[]>(docKey(conversationId), (old) =>
        old ? [doc, ...old] : [doc]
      );
      toast.success(`"${doc.filename}" uploaded — indexing...`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Upload failed";
      toast.error(msg);
    },
  });
}

export function useDeleteDocument(conversationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: documentService.delete,
    onMutate: async (documentId) => {
      await queryClient.cancelQueries({ queryKey: docKey(conversationId) });
      const previous = queryClient.getQueryData<Document[]>(docKey(conversationId));
      queryClient.setQueryData<Document[]>(docKey(conversationId), (old) =>
        old?.filter((d) => d.id !== documentId) ?? []
      );
      return { previous };
    },
    onError: (_err, _id, ctx) => {
      queryClient.setQueryData(docKey(conversationId), ctx?.previous);
      toast.error("Failed to delete document");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: docKey(conversationId) });
    },
  });
}
