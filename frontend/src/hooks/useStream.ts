/**
 * useStream — manages the streaming chat flow.
 *
 * Model is always stored in the conversation DB record — the stream endpoints
 * read it from there. We no longer pass a model override in the request body.
 */

import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { streamChat, streamRegenerate } from "@/lib/sse";
import { useChatStore } from "@/store/chat";
import { conversationKey } from "@/hooks/useConversations";
import type { Message } from "@/types/api";

export function useStream(conversationId: string) {
  const queryClient = useQueryClient();
  const {
    startStreaming,
    appendStreamToken,
    stopStreaming,
    clearStreaming,
    addToolCall,
    resolveToolCall,
  } = useChatStore();

  const sendMessage = useCallback(
    async (content: string, attachedDocIds?: string[]) => {
      const tempId = `temp-${Date.now()}`;
      const optimisticUserMessage: Message = {
        id: tempId,
        conversation_id: conversationId,
        role: "user",
        content,
        content_type: "text",
        token_count: null,
        is_edited: false,
        // Show attachment chips optimistically in the message bubble
        metadata: attachedDocIds?.length
          ? { attachments: attachedDocIds.map((id) => ({ doc_id: id, filename: "" })) }
          : {},
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData(
        conversationKey(conversationId),
        (old: { messages: Message[] } | undefined) =>
          old ? { ...old, messages: [...old.messages, optimisticUserMessage] } : undefined
      );

      const abortController = startStreaming(conversationId);

      try {
        await streamChat(
          conversationId,
          content,
          {
            onToken: (token) => appendStreamToken(token),
            onDone: () => {
              stopStreaming();
              queryClient.invalidateQueries({ queryKey: conversationKey(conversationId) });
              queryClient.invalidateQueries({ queryKey: ["conversations"] });
              setTimeout(clearStreaming, 400);
              // Re-fetch after 3s to catch async title generation
              setTimeout(() => {
                queryClient.invalidateQueries({ queryKey: ["conversations"] });
                queryClient.invalidateQueries({ queryKey: conversationKey(conversationId) });
              }, 3000);
            },
            onError: (message) => {
              stopStreaming();
              toast.error(`AI error: ${message}`);
              queryClient.setQueryData(
                conversationKey(conversationId),
                (old: { messages: Message[] } | undefined) =>
                  old ? { ...old, messages: old.messages.filter((m) => m.id !== tempId) } : undefined
              );
            },
            onClose: () => stopStreaming(),
            onToolUse: (toolName, input) => addToolCall(toolName, input),
            onToolResult: (toolName, result, isError) => resolveToolCall(toolName, result, isError),
          },
          abortController.signal,
          attachedDocIds,
        );
      } catch (error) {
        stopStreaming();
        if ((error as Error).name !== "AbortError") {
          toast.error("Failed to send message");
        }
      }
    },
    [conversationId, queryClient, startStreaming, appendStreamToken, stopStreaming, clearStreaming, addToolCall, resolveToolCall]
  );

  const regenerateLastMessage = useCallback(async () => {
    const abortController = startStreaming(conversationId);
    try {
      await streamRegenerate(
        conversationId,
        {
          onToken: (token) => appendStreamToken(token),
          onDone: () => {
            stopStreaming();
            queryClient.invalidateQueries({ queryKey: conversationKey(conversationId) });
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
            setTimeout(clearStreaming, 400);
            setTimeout(() => queryClient.invalidateQueries({ queryKey: ["conversations"] }), 3000);
          },
          onError: (message) => {
            stopStreaming();
            toast.error(`Regeneration failed: ${message}`);
          },
          onClose: () => stopStreaming(),
          onToolUse: (toolName, input) => addToolCall(toolName, input),
          onToolResult: (toolName, result, isError) => resolveToolCall(toolName, result, isError),
        },
        abortController.signal,
      );
    } catch (error) {
      stopStreaming();
      if ((error as Error).name !== "AbortError") {
        toast.error("Failed to regenerate response");
      }
    }
  }, [conversationId, queryClient, startStreaming, appendStreamToken, stopStreaming, clearStreaming, addToolCall, resolveToolCall]);

  return { sendMessage, regenerateLastMessage };
}
