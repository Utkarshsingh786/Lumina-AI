"use client";

import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, Sparkles, Cpu, ChevronDown } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { PersonaSelector } from "./PersonaSelector";
import { ShareButton } from "./ShareButton";
import { ToolCallCard } from "./ToolCallCard";
import { TypingIndicator } from "./TypingIndicator";
import { MessageInput } from "./MessageInput";
import { useConversation } from "@/hooks/useConversations";
import { useStream } from "@/hooks/useStream";
import { useChatStore, useStreamingContent } from "@/store/chat";
import { scrollToBottom } from "@/lib/utils";
import type { Message } from "@/types/api";

interface ChatWindowProps {
  conversationId: string;
}

const CONVERSATION_STARTERS = [
  { icon: "✍️", title: "Write something", prompt: "Help me write a professional email to..." },
  { icon: "💡", title: "Brainstorm ideas", prompt: "Give me 10 creative ideas for..." },
  { icon: "🔍", title: "Research a topic", prompt: "Explain the concept of..." },
  { icon: "🐛", title: "Debug code", prompt: "Help me debug this code:" },
];

const PERSONA_LABELS: Record<string, string> = {
  general: "General",
  coding: "Coding",
  research: "Research",
  writing: "Writing",
  data: "Data",
  support: "Support",
};

export function ChatWindow({ conversationId }: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { data: conversation, isLoading } = useConversation(conversationId);
  const { sendMessage, regenerateLastMessage } = useStream(conversationId);
  const streaming = useChatStore((s) => s.streaming);
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);
  const streamingContent = useStreamingContent(conversationId);
  const [showPersonaDropdown, setShowPersonaDropdown] = useState(false);
  const personaDropdownRef = useRef<HTMLDivElement>(null);

  const isStreaming =
    streaming?.conversationId === conversationId && streaming.isStreaming;
  const isWaitingForFirstToken =
    isStreaming && (streamingContent === null || streamingContent === "");

  const activeToolCalls =
    streaming?.conversationId === conversationId ? (streaming.toolCalls ?? []) : [];
  const hasToolCalls = activeToolCalls.length > 0;

  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);

  // Close persona dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        personaDropdownRef.current &&
        !personaDropdownRef.current.contains(e.target as Node)
      ) {
        setShowPersonaDropdown(false);
      }
    };
    if (showPersonaDropdown) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showPersonaDropdown]);

  useEffect(() => {
    scrollToBottom(scrollRef.current, isStreaming ? "instant" : "smooth");
  }, [conversation?.messages, streamingContent, isStreaming, activeToolCalls.length]);

  const messages: Message[] = conversation?.messages ?? [];
  const hasMessages = messages.length > 0;

  const lastAssistantIdx = messages.reduce(
    (acc, m, i) => (m.role === "assistant" ? i : acc),
    -1
  );

  const title = conversation?.title ?? "New Chat";
  const model = conversation?.model;
  const persona = conversation?.persona ?? "general";
  const personaLabel = PERSONA_LABELS[persona] ?? persona;

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ────────────────────────────────────── */}
      <div className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-neutral-800 bg-neutral-900/60 backdrop-blur-sm">
        {/* Mobile hamburger */}
        <button
          onClick={toggleSidebar}
          className="md:hidden p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors flex-shrink-0"
          title="Open sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Title */}
        <div className="flex-1 min-w-0">
          <h1 className="text-sm font-semibold text-neutral-200 truncate">{title}</h1>
          {model && (
            <span className="flex items-center gap-1 text-xs text-neutral-500 mt-0.5">
              <Cpu className="w-3 h-3" />
              {model}
            </span>
          )}
        </div>

        {/* Share button — only shown when conversation has messages */}
        {conversation && hasMessages && (
          <ShareButton conversation={conversation} />
        )}

        {/* Persona switcher — always visible in header */}
        <div className="relative flex-shrink-0" ref={personaDropdownRef}>
          <button
            onClick={() => setShowPersonaDropdown((v) => !v)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-neutral-700 bg-neutral-800 hover:bg-neutral-700 hover:border-neutral-600 transition-colors text-xs text-neutral-300"
            title="Switch persona"
          >
            <span>{conversation ? (
              // Show the icon from the persona if available, otherwise just label
              personaLabel
            ) : "Mode"}</span>
            <ChevronDown className="w-3 h-3 text-neutral-500" />
          </button>

          <AnimatePresence>
            {showPersonaDropdown && (
              <motion.div
                initial={{ opacity: 0, y: -4, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.96 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-full mt-1 z-30 bg-neutral-800 border border-neutral-700 rounded-xl shadow-2xl overflow-hidden"
              >
                <PersonaSelector
                  conversationId={conversationId}
                  currentPersona={persona}
                  compact
                  onSelect={() => setShowPersonaDropdown(false)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ── Messages area ─────────────────────────────── */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto scrollbar-thin"
      >
        {isLoading ? (
          <LoadingSkeleton />
        ) : !hasMessages && !isStreaming ? (
          <EmptyState
            onSelectStarter={sendMessage}
            conversationId={conversationId}
            currentPersona={persona}
          />
        ) : (
          <div className="max-w-3xl mx-auto py-6 space-y-1">
            <AnimatePresence initial={false}>
              {messages.map((message: Message, idx) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  isEditing={editingMessageId === message.id}
                  onEditStart={() => setEditingMessageId(message.id)}
                  onEditCancel={() => setEditingMessageId(null)}
                  onEditSave={(content) => {
                    setEditingMessageId(null);
                    sendMessage(content);
                  }}
                  onRegenerate={
                    !isStreaming && idx === lastAssistantIdx
                      ? regenerateLastMessage
                      : undefined
                  }
                />
              ))}

              {hasToolCalls && (
                <div key="tool-calls" className="px-4 space-y-1">
                  {activeToolCalls.map((tc, i) => (
                    <ToolCallCard key={`${tc.tool_name}-${i}`} toolCall={tc} />
                  ))}
                </div>
              )}

              {isStreaming && streamingContent !== null && streamingContent !== "" && (
                <MessageBubble
                  key="streaming"
                  message={{
                    id: "streaming",
                    conversation_id: conversationId,
                    role: "assistant",
                    content: streamingContent,
                    content_type: "text",
                    token_count: null,
                    is_edited: false,
                    metadata: {},
                    created_at: new Date().toISOString(),
                  }}
                  isStreaming
                />
              )}

              {isWaitingForFirstToken && !hasToolCalls && (
                <TypingIndicator key="typing" />
              )}
            </AnimatePresence>

            <div className="h-4" />
          </div>
        )}
      </div>

      {/* ── Input area ────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-neutral-800 bg-neutral-900/80 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <MessageInput
            onSend={sendMessage}
            conversationId={conversationId}
            conversationModel={conversation?.model ?? ""}
            hasMessages={hasMessages}
          />
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  onSelectStarter,
  conversationId,
  currentPersona,
}: {
  onSelectStarter: (prompt: string) => void;
  conversationId: string;
  currentPersona: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] px-4 gap-8">
      <div className="flex flex-col items-center">
        <div className="w-12 h-12 rounded-2xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center mb-4">
          <Sparkles className="w-6 h-6 text-brand-400" />
        </div>
        <h2 className="text-xl font-semibold text-neutral-100 mb-2">How can I help?</h2>
        <p className="text-neutral-400 text-sm text-center">
          Ask me anything — I can write, analyze, code, research, and more.
        </p>
      </div>

      <PersonaSelector conversationId={conversationId} currentPersona={currentPersona} />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
        {CONVERSATION_STARTERS.map((starter) => (
          <button
            key={starter.title}
            onClick={() => onSelectStarter(starter.prompt)}
            className="group flex items-start gap-3 p-4 bg-neutral-800/80 hover:bg-neutral-700/80 border border-neutral-700 hover:border-neutral-600 rounded-xl transition-all text-left"
          >
            <span className="text-xl">{starter.icon}</span>
            <div>
              <p className="text-sm font-medium text-neutral-200 group-hover:text-white">
                {starter.title}
              </p>
              <p className="text-xs text-neutral-500 mt-0.5 line-clamp-1">{starter.prompt}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="max-w-3xl mx-auto py-6 space-y-6 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex gap-3 px-4">
          <div className="w-8 h-8 rounded-full bg-neutral-800 flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-neutral-800 rounded w-3/4" />
            <div className="h-4 bg-neutral-800 rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}
