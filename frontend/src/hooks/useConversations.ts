/**
 * React Query hooks for conversations.
 *
 * Why React Query over manual fetch:
 * - Automatic caching, background refetch, stale-while-revalidate
 * - Optimistic updates for instant UI feedback
 * - Automatic retry on network errors
 * - Query invalidation cascades: deleting a conv invalidates the list
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { conversationService } from "@/services/conversation.service";
import { useChatStore } from "@/store/chat";
import type { ConversationListItem, PaginatedResponse } from "@/types/api";

export const CONVERSATIONS_KEY = ["conversations"] as const;
export const conversationKey = (id: string) => ["conversation", id] as const;

export function useConversations() {
  return useQuery({
    queryKey: CONVERSATIONS_KEY,
    queryFn: () => conversationService.list(),
    staleTime: 30_000, // 30s — list is fairly stable
    select: (data) => data.items,
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: conversationKey(id!),
    queryFn: () => conversationService.get(id!),
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: conversationService.create,
    onSuccess: (newConv) => {
      queryClient.setQueryData<PaginatedResponse<ConversationListItem>>(
        CONVERSATIONS_KEY,
        (old) => old
          ? { ...old, items: [newConv as ConversationListItem, ...old.items] }
          : { items: [newConv as ConversationListItem], total: 1, page: 1, page_size: 50, has_next: false, has_prev: false }
      );
      queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
      router.push(`/${newConv.id}`);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to create conversation";
      toast.error(msg);
    },
  });
}

/**
 * Smart "New Chat" hook.
 *
 * Rules:
 * 1. If the current page is already an empty conversation → stay there (no new conv)
 * 2. If there's another empty conversation in the list → navigate to it
 * 3. Otherwise create a new one, passing the currently selected model
 */
export function useNewChat(currentConversationId?: string) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const selectedModel = useChatStore((s) => s.selectedModel);
  const { mutate: createConversation, isPending } = useCreateConversation();

  const newChat = () => {
    const allConvs = queryClient.getQueryData<PaginatedResponse<ConversationListItem>>(CONVERSATIONS_KEY);
    const list = allConvs?.items ?? [];

    // Is the current conversation already empty?
    if (currentConversationId) {
      const current = list.find((c) => c.id === currentConversationId);
      if (current && current.message_count === 0) {
        // Already on an empty chat — do nothing
        return;
      }
    }

    // Is there any other empty conversation we can reuse?
    const existingEmpty = list.find(
      (c) => c.message_count === 0 && c.id !== currentConversationId
    );
    if (existingEmpty) {
      router.push(`/${existingEmpty.id}`);
      return;
    }

    // Create a fresh one with the selected model
    createConversation({ model: selectedModel ?? undefined });
  };

  return { newChat, isPending };
}

export function useUpdateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; title?: string; model?: string; is_pinned?: boolean; persona?: string }) =>
      conversationService.update(id, data),
    onSuccess: (updated) => {
      // Update in list cache
      queryClient.setQueryData<PaginatedResponse<ConversationListItem>>(
        CONVERSATIONS_KEY,
        (old) => old
          ? { ...old, items: old.items.map((c) => (c.id === updated.id ? { ...c, ...updated } : c)) }
          : old
      );
      queryClient.invalidateQueries({ queryKey: conversationKey(updated.id) });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: conversationService.delete,
    onMutate: async (id) => {
      // Optimistically remove from list
      await queryClient.cancelQueries({ queryKey: CONVERSATIONS_KEY });
      const previous = queryClient.getQueryData<PaginatedResponse<ConversationListItem>>(CONVERSATIONS_KEY);
      queryClient.setQueryData<PaginatedResponse<ConversationListItem>>(
        CONVERSATIONS_KEY,
        (old) => old
          ? { ...old, items: old.items.filter((c) => c.id !== id) }
          : old
      );
      return { previous };
    },
    onError: (_err, _id, context) => {
      // Rollback on error
      queryClient.setQueryData(CONVERSATIONS_KEY, context?.previous);
      toast.error("Failed to delete conversation");
    },
    onSuccess: () => {
      router.push("/");
      toast.success("Conversation deleted");
    },
  });
}

export function useSubmitFeedback() {
  return useMutation({
    mutationFn: ({
      messageId,
      rating,
      comment,
    }: {
      messageId: string;
      rating: 1 | -1;
      comment?: string;
    }) => conversationService.submitFeedback(messageId, rating, comment),
    onSuccess: () => toast.success("Feedback recorded"),
    onError: () => toast.error("Failed to submit feedback"),
  });
}
