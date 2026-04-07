import { apiClient, getStoredAccessToken } from "@/lib/api";
import type {
  Conversation,
  ConversationDetail,
  ConversationListItem,
  Message,
  PaginatedResponse,
} from "@/types/api";

export const conversationService = {
  async list(page = 1, pageSize = 50): Promise<PaginatedResponse<ConversationListItem>> {
    const res = await apiClient.get<PaginatedResponse<ConversationListItem>>("/conversations", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },

  async create(data?: {
    title?: string;
    model?: string;
    persona?: string;
  }): Promise<Conversation> {
    const res = await apiClient.post<Conversation>("/conversations", data || {});
    return res.data;
  },

  async get(id: string): Promise<ConversationDetail> {
    const res = await apiClient.get<ConversationDetail>(`/conversations/${id}`);
    return res.data;
  },

  async update(
    id: string,
    data: Partial<{ title: string; model: string; persona: string; is_pinned: boolean; is_archived: boolean }>
  ): Promise<Conversation> {
    const res = await apiClient.patch<Conversation>(`/conversations/${id}`, data);
    return res.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/conversations/${id}`);
  },

  async submitFeedback(
    messageId: string,
    rating: 1 | -1,
    comment?: string
  ): Promise<void> {
    await apiClient.post(`/conversations/messages/${messageId}/feedback`, {
      rating,
      comment,
    });
  },

  async deleteMessage(messageId: string): Promise<void> {
    await apiClient.delete(`/conversations/messages/${messageId}`);
  },

  async editMessage(messageId: string, content: string): Promise<Message> {
    const res = await apiClient.patch<Message>(`/conversations/messages/${messageId}`, {
      content,
    });
    return res.data;
  },

  async export(id: string, format: "json" | "markdown" | "txt" = "markdown"): Promise<void> {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
    const token = getStoredAccessToken();
    const res = await fetch(
      `${baseUrl}/api/v1/conversations/${id}/export?format=${format}`,
      { headers: { Authorization: `Bearer ${token ?? ""}` } }
    );
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") ?? "";
    const filename =
      disposition.match(/filename="([^"]+)"/)?.[1] ??
      `conversation.${format === "markdown" ? "md" : format}`;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },

  async search(query: string): Promise<ConversationListItem[]> {
    const res = await apiClient.get<ConversationListItem[]>("/search", {
      params: { q: query, scope: "conversations" },
    });
    return res.data;
  },
};
