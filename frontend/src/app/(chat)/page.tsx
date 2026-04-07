/**
 * Home page — shown when no conversation is open.
 * Uses useNewChat so we don't create duplicates.
 */

"use client";

import { Sparkles } from "lucide-react";
import { useNewChat } from "@/hooks/useConversations";

export default function HomePage() {
  const { newChat, isPending } = useNewChat(undefined);

  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      <div className="text-center max-w-lg">
        <div className="w-16 h-16 rounded-2xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center mx-auto mb-6">
          <Sparkles className="w-8 h-8 text-brand-400" />
        </div>
        <h1 className="text-3xl font-bold text-neutral-100 mb-3">
          Welcome to Lumina
        </h1>
        <p className="text-neutral-400 mb-8 leading-relaxed">
          Your intelligent AI assistant. Ask questions, get help with writing,
          analyze data, debug code — whatever you need.
        </p>
        <button
          onClick={newChat}
          disabled={isPending}
          className="px-6 py-3 bg-brand-600 hover:bg-brand-500 text-white rounded-xl font-medium transition-colors disabled:opacity-50"
        >
          {isPending ? "Creating..." : "Start a conversation"}
        </button>
      </div>
    </div>
  );
}
