import { apiClient } from "@/lib/api";
import type { Document } from "@/types/api";

export const documentService = {
  async upload(conversationId: string, file: File): Promise<Document> {
    const form = new FormData();
    form.append("conversation_id", conversationId);
    form.append("file", file);
    const { data } = await apiClient.post<Document>("/documents", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  async list(conversationId: string): Promise<Document[]> {
    const { data } = await apiClient.get<Document[]>("/documents", {
      params: { conversation_id: conversationId },
    });
    return data;
  },

  async delete(documentId: string): Promise<void> {
    await apiClient.delete(`/documents/${documentId}`);
  },
};
