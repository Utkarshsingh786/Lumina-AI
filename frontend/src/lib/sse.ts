/**
 * SSE (Server-Sent Events) streaming client.
 *
 * Model is stored in the conversation DB record and read server-side.
 * The request body only contains the message content — no model override.
 */

import type { SSEDoneEvent, SSEEvent } from "@/types/api";
import { getStoredAccessToken } from "@/lib/api";

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onDone: (messageId: string, usage: SSEDoneEvent["usage"]) => void;
  onError: (message: string) => void;
  onClose?: () => void;
  onToolUse?: (toolName: string, input: Record<string, unknown>) => void;
  onToolResult?: (toolName: string, result: string, isError: boolean) => void;
}

export async function streamChat(
  conversationId: string,
  content: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const url = `${baseUrl}/api/v1/conversations/${conversationId}/chat`;
  const token = getStoredAccessToken();
  if (!token) { callbacks.onError("Not authenticated"); return; }

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ content, stream: true }),
      signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    callbacks.onError("Network error — failed to connect");
    return;
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    callbacks.onError(errorData.message || `Request failed: ${response.status}`);
    return;
  }

  await _readSSEStream(response, callbacks);
}

export async function streamRegenerate(
  conversationId: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const url = `${baseUrl}/api/v1/conversations/${conversationId}/regenerate`;
  const token = getStoredAccessToken();
  if (!token) { callbacks.onError("Not authenticated"); return; }

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ stream: true }),
      signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") return;
    callbacks.onError("Network error — failed to connect");
    return;
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    callbacks.onError(errorData.message || `Request failed: ${response.status}`);
    return;
  }

  await _readSSEStream(response, callbacks);
}

async function _readSSEStream(response: Response, callbacks: StreamCallbacks): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) { callbacks.onError("No response body"); return; }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const eventText of events) {
        if (!eventText.trim() || eventText.startsWith(":")) continue;
        const lines = eventText.split("\n");
        let data = "";
        for (const line of lines) {
          if (line.startsWith("data: ")) data = line.slice(6).trim();
        }
        if (!data) continue;
        try {
          const parsed: SSEEvent = JSON.parse(data);
          _handleSSEEvent(parsed, callbacks);
        } catch { /* skip malformed */ }
      }
    }
  } catch (error) {
    if ((error as Error).name !== "AbortError") callbacks.onError("Stream connection lost");
  } finally {
    reader.releaseLock();
    callbacks.onClose?.();
  }
}

function _handleSSEEvent(event: SSEEvent, callbacks: StreamCallbacks): void {
  switch (event.type) {
    case "token":
      callbacks.onToken(event.content);
      break;
    case "done":
      callbacks.onDone(event.message_id, event.usage);
      break;
    case "error":
      callbacks.onError(event.message);
      break;
    case "tool_use":
      callbacks.onToolUse?.(event.tool_name, event.input);
      break;
    case "tool_result":
      callbacks.onToolResult?.(event.tool_name, event.result, event.is_error);
      break;
  }
}
