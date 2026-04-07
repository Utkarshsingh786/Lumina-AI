/**
 * Chat UI store — manages streaming state, active conversation, and UI flags.
 *
 * Separation from React Query:
 * - React Query owns server state (conversations list, messages from API)
 * - Zustand owns UI state (currently streaming tokens, which conv is open)
 * - This prevents unnecessary re-fetches triggered by UI interactions
 */

import { create } from "zustand";
import type { ActiveToolCall, Message } from "@/types/api";

interface StreamingMessage {
  conversationId: string;
  content: string;
  isStreaming: boolean;
  abortController: AbortController | null;
  /** Tool calls active during this stream (shown as cards above the text) */
  toolCalls: ActiveToolCall[];
}

interface ChatState {
  activeConversationId: string | null;
  streaming: StreamingMessage | null;
  // Optimistic messages: shown immediately before server confirms
  optimisticMessages: Record<string, Message[]>;
  /** Model chosen in the UI selector; null = use conversation default */
  selectedModel: string | null;
  /** Mobile sidebar visibility */
  sidebarOpen: boolean;

  setActiveConversation: (id: string | null) => void;
  setSelectedModel: (model: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  startStreaming: (conversationId: string) => AbortController;
  appendStreamToken: (token: string) => void;
  stopStreaming: () => void;
  addOptimisticMessage: (conversationId: string, message: Message) => void;
  clearOptimisticMessages: (conversationId: string) => void;
  abortStream: () => void;
  /** Fully clear streaming state (called after query refetch completes) */
  clearStreaming: () => void;
  /** Called when the AI requests a tool call — shows spinner card */
  addToolCall: (toolName: string, input: Record<string, unknown>) => void;
  /** Called when the tool result arrives — updates card to done/error */
  resolveToolCall: (toolName: string, result: string, isError: boolean) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  activeConversationId: null,
  streaming: null,
  optimisticMessages: {},
  selectedModel: null,
  sidebarOpen: false,

  setActiveConversation: (id) => set({ activeConversationId: id }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  startStreaming: (conversationId) => {
    const abortController = new AbortController();
    set({
      streaming: {
        conversationId,
        content: "",
        isStreaming: true,
        abortController,
        toolCalls: [],
      },
    });
    return abortController;
  },

  appendStreamToken: (token) =>
    set((state) => ({
      streaming: state.streaming
        ? { ...state.streaming, content: state.streaming.content + token }
        : null,
    })),

  stopStreaming: () =>
    set((state) => ({
      streaming: state.streaming ? { ...state.streaming, isStreaming: false } : null,
    })),

  addOptimisticMessage: (conversationId, message) =>
    set((state) => ({
      optimisticMessages: {
        ...state.optimisticMessages,
        [conversationId]: [
          ...(state.optimisticMessages[conversationId] || []),
          message,
        ],
      },
    })),

  clearOptimisticMessages: (conversationId) =>
    set((state) => {
      const { [conversationId]: _, ...rest } = state.optimisticMessages;
      return { optimisticMessages: rest };
    }),

  abortStream: () => {
    const { streaming } = get();
    streaming?.abortController?.abort();
    set({ streaming: null });
  },

  clearStreaming: () => set({ streaming: null }),

  addToolCall: (toolName, input) =>
    set((state) => ({
      streaming: state.streaming
        ? {
            ...state.streaming,
            toolCalls: [
              ...state.streaming.toolCalls,
              { tool_name: toolName, input, status: "running" },
            ],
          }
        : null,
    })),

  resolveToolCall: (toolName, result, isError) =>
    set((state) => ({
      streaming: state.streaming
        ? {
            ...state.streaming,
            toolCalls: state.streaming.toolCalls.map((tc) =>
              tc.tool_name === toolName && tc.status === "running"
                ? { ...tc, status: isError ? "error" : "done", result }
                : tc
            ),
          }
        : null,
    })),
}));

// Selector hooks for common patterns
export const useIsStreaming = (conversationId: string) =>
  useChatStore((s) => s.streaming?.conversationId === conversationId && s.streaming.isStreaming);

export const useStreamingContent = (conversationId: string) =>
  useChatStore((s) =>
    s.streaming?.conversationId === conversationId ? s.streaming.content : null
  );
