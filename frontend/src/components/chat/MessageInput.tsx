"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp, Paperclip, Square, Lock } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/store/chat";
import { apiClient } from "@/lib/api";
import { ModelSelector } from "./ModelSelector";
import { MicButton } from "@/components/voice/MicButton";
import { useVoice } from "@/hooks/useVoice";
import type { ModelsResponse } from "@/types/api";
import { useUploadDocument } from "@/hooks/useDocuments";
import { useUpdateConversation } from "@/hooks/useConversations";

interface MessageInputProps {
  onSend: (content: string) => void;
  conversationId: string;
  /** The model stored on the conversation in the DB */
  conversationModel: string;
  /** Whether this conversation already has messages — locks the model selector */
  hasMessages: boolean;
  disabled?: boolean;
  placeholder?: string;
}

const SUGGESTED_PROMPTS = [
  "Explain this in simple terms",
  "Write a summary",
  "Give me a code example",
  "What are the pros and cons?",
];

async function fetchModels(): Promise<ModelsResponse> {
  const { data } = await apiClient.get("/health/models");
  return data;
}

export function MessageInput({
  onSend,
  conversationId,
  conversationModel,
  hasMessages,
  disabled = false,
  placeholder = "Message Lumina...",
}: MessageInputProps) {
  const [content, setContent] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { streaming, abortStream, selectedModel, setSelectedModel } = useChatStore();
  const isStreaming = streaming?.conversationId === conversationId && streaming.isStreaming;
  const { mutate: uploadDocument, isPending: isUploading } = useUploadDocument(conversationId);
  const { mutate: updateConversation } = useUpdateConversation();

  const { recordState, interimText, toggleRecording } = useVoice({
    onTranscript: (text, autoSubmit) => {
      if (autoSubmit && !disabled && !isStreaming) {
        // Web Speech API path: send immediately like ChatGPT
        onSend(text.trim());
        setContent("");
        setShowSuggestions(false);
      } else {
        // Whisper path: populate the box so the user can review/edit
        setContent((prev) => prev ? `${prev} ${text}` : text);
        textareaRef.current?.focus();
      }
    },
    onError: (msg) => toast.error(msg),
  });

  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: fetchModels,
    staleTime: 5 * 60 * 1000,
  });

  const models = modelsData?.models ?? [];
  const defaultModel = modelsData?.default ?? "";

  // Sync Zustand selectedModel from the conversation's stored model.
  // This ensures the selector always reflects DB truth, not stale Zustand state
  // when navigating between conversations.
  useEffect(() => {
    if (conversationModel) {
      setSelectedModel(conversationModel);
    } else if (!selectedModel && defaultModel) {
      setSelectedModel(defaultModel);
    }
  }, [conversationId, conversationModel, defaultModel]);

  // The model shown in the selector = what's in the DB (via selectedModel)
  const currentModel = selectedModel ?? conversationModel ?? defaultModel;

  const handleModelChange = (newModel: string) => {
    if (hasMessages) return; // locked — should never be called, but guard anyway
    setSelectedModel(newModel);
    // Persist model choice to DB immediately so the backend uses it
    updateConversation({ id: conversationId, model: newModel });
  };

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [content]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, [conversationId]);

  const handleSend = useCallback(() => {
    const trimmed = content.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSend(trimmed);
    setContent("");
    setShowSuggestions(false);
  }, [content, disabled, isStreaming, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = content.trim().length > 0 && !disabled && !isStreaming;

  return (
    <div className="relative">
      {/* Suggested prompts */}
      <AnimatePresence>
        {showSuggestions && !content && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="absolute bottom-full mb-2 left-0 right-0 flex flex-wrap gap-2 px-2"
          >
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                onClick={() => { setContent(prompt); textareaRef.current?.focus(); }}
                className="text-xs px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded-full text-neutral-300 transition-colors"
              >
                {prompt}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input container */}
      <div
        className={cn(
          "relative flex flex-col rounded-2xl border transition-all",
          "bg-neutral-800/80 backdrop-blur-sm",
          content || showSuggestions
            ? "border-brand-500/50 shadow-[0_0_0_1px_rgba(14,165,233,0.2)]"
            : "border-neutral-700",
          "p-2"
        )}
      >
        {/* Textarea row */}
        <div className="flex items-end gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,text/plain,text/markdown,application/pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadDocument(file);
              e.target.value = "";
            }}
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || isStreaming}
            className={cn(
              "flex-shrink-0 p-2 rounded-xl transition-colors",
              isUploading ? "text-brand-400 cursor-wait" : "text-neutral-500 hover:text-neutral-300"
            )}
            title={isUploading ? "Uploading..." : "Attach file for RAG"}
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <MicButton
            recordState={recordState}
            onClick={toggleRecording}
            disabled={isStreaming}
          />

          <div className="relative flex-1">
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              placeholder={
                recordState === "recording" && interimText
                  ? ""
                  : isStreaming
                  ? "Generating..."
                  : placeholder
              }
              disabled={disabled}
              rows={1}
              className={cn(
                "w-full bg-transparent resize-none outline-none",
                "text-sm text-neutral-100 placeholder:text-neutral-500",
                "min-h-[36px] max-h-[200px] py-2 px-1",
                "scrollbar-thin scrollbar-thumb-neutral-600"
              )}
            />
            {/* Live interim transcript overlay — shown during Web Speech recording */}
            {recordState === "recording" && interimText && (
              <div className="absolute inset-0 flex items-center py-2 px-1 pointer-events-none">
                <span className="text-sm text-neutral-400 italic">{interimText}</span>
              </div>
            )}
          </div>

          <button
            onClick={isStreaming ? abortStream : handleSend}
            disabled={!isStreaming && !canSend}
            className={cn(
              "flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all",
              isStreaming
                ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                : canSend
                ? "bg-brand-600 text-white hover:bg-brand-500 shadow-md"
                : "bg-neutral-700 text-neutral-500 cursor-not-allowed"
            )}
            title={isStreaming ? "Stop generating" : "Send message"}
          >
            {isStreaming ? <Square className="w-3 h-3 fill-current" /> : <ArrowUp className="w-4 h-4" />}
          </button>
        </div>

        {/* Model selector / locked model row */}
        {models.length > 0 && (
          <div className="flex items-center gap-2 mt-1.5 px-1">
            {hasMessages ? (
              /* Locked — conversation is in progress */
              <div
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-neutral-800 border border-neutral-700 text-neutral-500"
                title="Model is locked for this conversation. Start a new chat to use a different model."
              >
                <Lock className="w-3 h-3" />
                <span className="max-w-[140px] truncate">{currentModel}</span>
              </div>
            ) : (
              <ModelSelector
                models={models}
                value={currentModel}
                onChange={handleModelChange}
                disabled={isStreaming}
              />
            )}
            <span className="text-xs text-neutral-600">Shift+Enter for new line</span>
          </div>
        )}
      </div>
    </div>
  );
}
