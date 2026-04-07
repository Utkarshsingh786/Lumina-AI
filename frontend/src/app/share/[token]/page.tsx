"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Sparkles, MessageSquare, AlertCircle, Loader2 } from "lucide-react";
import { MarkdownRenderer } from "@/components/shared/MarkdownRenderer";
import type { ConversationDetail } from "@/types/api";

async function fetchShared(token: string): Promise<ConversationDetail> {
  const base = process.env.NEXT_PUBLIC_API_URL || "";
  const res = await fetch(`${base}/api/v1/share/${token}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "Conversation not found or link revoked");
  }
  return res.json();
}

export default function SharedConversationPage() {
  const { token } = useParams<{ token: string }>();
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetchShared(token)
      .then(setConversation)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  if (error || !conversation) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 px-4">
        <div className="text-center max-w-sm">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-lg font-semibold text-neutral-100 mb-2">Link not found</h1>
          <p className="text-sm text-neutral-400">{error ?? "This share link is invalid or has been revoked."}</p>
        </div>
      </div>
    );
  }

  const messages = conversation.messages.filter(
    (m) => m.role === "user" || m.role === "assistant"
  );

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-brand-400" />
            <span className="font-semibold text-neutral-100">Lumina</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            <MessageSquare className="w-3.5 h-3.5" />
            <span>{messages.length} messages</span>
            <span className="text-neutral-700">·</span>
            <span className="capitalize">{conversation.model}</span>
          </div>
        </div>
      </header>

      {/* Conversation */}
      <main className="max-w-3xl mx-auto px-4 py-8">
        {/* Title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-neutral-100 mb-1">{conversation.title}</h1>
          <p className="text-sm text-neutral-500">
            Shared conversation · {conversation.model} · {conversation.persona} mode
          </p>
        </div>

        {/* Messages */}
        <div className="space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={
                msg.role === "user"
                  ? "flex justify-end"
                  : "flex justify-start"
              }
            >
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center flex-shrink-0 mr-3 mt-0.5">
                  <Sparkles className="w-3.5 h-3.5 text-white" />
                </div>
              )}
              <div
                className={
                  msg.role === "user"
                    ? "max-w-[80%] bg-neutral-800 rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-neutral-100"
                    : "max-w-[85%] text-sm text-neutral-100"
                }
              >
                {msg.role === "assistant" ? (
                  <MarkdownRenderer content={msg.content} />
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}
                <p className="text-xs text-neutral-600 mt-1">
                  {new Date(msg.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-neutral-800 text-center">
          <p className="text-xs text-neutral-600">
            Shared via{" "}
            <a href="/" className="text-brand-400 hover:text-brand-300">
              Lumina AI
            </a>{" "}
            · Read-only view
          </p>
        </div>
      </main>
    </div>
  );
}
