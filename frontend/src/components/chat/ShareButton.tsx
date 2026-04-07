"use client";

import { useState } from "react";
import { Share2, Link, X, Check, Loader2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { apiClient } from "@/lib/api";
import type { Conversation } from "@/types/api";
import { cn } from "@/lib/utils";

interface ShareButtonProps {
  conversation: Conversation;
}

async function shareConversation(conversationId: string): Promise<Conversation> {
  const { data } = await apiClient.post(`/conversations/${conversationId}/share`);
  return data;
}

async function unshareConversation(conversationId: string): Promise<void> {
  await apiClient.delete(`/conversations/${conversationId}/share`);
}

export function ShareButton({ conversation }: ShareButtonProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const queryClient = useQueryClient();

  const shareUrl = conversation.share_token
    ? `${window.location.origin}/share/${conversation.share_token}`
    : null;

  const shareMutation = useMutation({
    mutationFn: () => shareConversation(conversation.id),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      toast.success("Share link generated");
    },
    onError: () => toast.error("Failed to generate share link"),
  });

  const unshareMutation = useMutation({
    mutationFn: () => unshareConversation(conversation.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      toast.success("Share link revoked");
      setOpen(false);
    },
    onError: () => toast.error("Failed to revoke share link"),
  });

  const copyLink = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success("Link copied to clipboard");
    } catch {
      toast.error("Failed to copy link");
    }
  };

  const isPending = shareMutation.isPending || unshareMutation.isPending;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        title="Share conversation"
        className={cn(
          "p-1.5 rounded-lg transition-colors",
          conversation.is_public
            ? "text-brand-400 hover:text-brand-300 hover:bg-brand-500/10"
            : "text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800"
        )}
      >
        <Share2 className="w-4 h-4" />
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 top-8 z-50 w-80 rounded-xl border border-neutral-700 bg-neutral-900 shadow-2xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-neutral-100">Share conversation</h3>
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded text-neutral-500 hover:text-neutral-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {conversation.is_public && shareUrl ? (
              <>
                <p className="text-xs text-neutral-400 mb-3">
                  Anyone with this link can view the conversation (read-only, no auth required).
                </p>

                {/* Link preview */}
                <div className="flex items-center gap-2 bg-neutral-800 rounded-lg px-3 py-2 mb-3">
                  <Link className="w-3.5 h-3.5 text-neutral-500 flex-shrink-0" />
                  <span className="text-xs text-neutral-300 truncate flex-1">{shareUrl}</span>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={copyLink}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition-colors"
                  >
                    {copied ? (
                      <><Check className="w-3.5 h-3.5" /> Copied!</>
                    ) : (
                      <><Link className="w-3.5 h-3.5" /> Copy link</>
                    )}
                  </button>
                  <button
                    onClick={() => unshareMutation.mutate()}
                    disabled={isPending}
                    className="px-3 py-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Revoke"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="text-xs text-neutral-400 mb-4">
                  Generate a public link so anyone can view this conversation without signing in.
                </p>
                <button
                  onClick={() => shareMutation.mutate()}
                  disabled={isPending}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {isPending ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Generating link…</>
                  ) : (
                    <><Share2 className="w-4 h-4" /> Generate share link</>
                  )}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
