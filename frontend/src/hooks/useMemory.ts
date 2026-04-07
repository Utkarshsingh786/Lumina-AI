import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { apiClient } from "@/lib/api";
import type { MemoryEntry, PaginatedResponse } from "@/types/api";

const MEMORY_KEY = ["memory"] as const;

async function listMemories(includeInactive = false): Promise<PaginatedResponse<MemoryEntry>> {
  const { data } = await apiClient.get<PaginatedResponse<MemoryEntry>>("/memory", {
    params: { include_inactive: includeInactive, page_size: 100 },
  });
  return data;
}

async function toggleMemory(id: string, isActive: boolean): Promise<MemoryEntry> {
  const { data } = await apiClient.patch<MemoryEntry>(`/memory/${id}`, { is_active: isActive });
  return data;
}

async function deleteMemory(id: string): Promise<void> {
  await apiClient.delete(`/memory/${id}`);
}

export function useMemory(includeInactive = false) {
  return useQuery({
    queryKey: [...MEMORY_KEY, includeInactive],
    queryFn: () => listMemories(includeInactive),
    staleTime: 30_000,
    select: (data) => data.items,
  });
}

export function useToggleMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      toggleMemory(id, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMORY_KEY });
    },
    onError: () => toast.error("Failed to update memory"),
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMemory,
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: MEMORY_KEY });
      const previous = queryClient.getQueryData(MEMORY_KEY);
      // Optimistically remove from all memory queries
      queryClient.setQueriesData<PaginatedResponse<MemoryEntry>>(
        { queryKey: MEMORY_KEY },
        (old) => old ? { ...old, items: old.items.filter((m) => m.id !== id) } : old
      );
      return { previous };
    },
    onError: (_err, _id, context) => {
      queryClient.setQueryData(MEMORY_KEY, context?.previous);
      toast.error("Failed to delete memory");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MEMORY_KEY });
      toast.success("Memory deleted");
    },
  });
}
