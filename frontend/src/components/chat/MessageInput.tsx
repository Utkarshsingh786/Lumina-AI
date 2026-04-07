"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp, FileText, Loader2, Paperclip, Square, Lock, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/store/chat";
import { apiClient } from "@/lib/api";
import { ModelSelector } from "./ModelSelector";
import { MicButton } from "@/components/voice/MicButton";
import { useVoice } from "@/hooks/useVoice";
import type { ModelsResponse, Document } from "@/types/api";
import { useUpdateConversation } from "@/hooks/useConversations";
import { documentService } from "@/services/document.service";

interface MessageInputProps {
  onSend: (content: string, attachedDocIds?: string[]) => void;
  conversationId: string;
  conversationModel: string;
  hasMessages: boolean;
  disabled?: boolean;
  placeholder?: string;
}

interface PendingAttachment {
  /** Local UUID — only used as React key before upload completes */
  localId: string;
  filename: string;
  /** Set once the upload succeeds */
  docId?: string;
  status: "uploading" | "ready" | "error";
  errorMsg?: string;
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
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { streaming, abortStream, selectedModel, setSelectedModel } = useChatStore();
  const isStreaming = streaming?.conversationId === conversationId && streaming.isStreaming;
  const { mutate: updateConversation } = useUpdateConversation();

  const { recordState, interimText, toggleRecording } = useVoice({
    onTranscript: (text, autoSubmit) => {
      if (autoSubmit && !disabled && !isStreaming) {
        handleSendWithAttachments(text.trim());
      } else {
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

  useEffect(() => {
    if (conversationModel) {
      setSelectedModel(conversationModel);
    } else if (!selectedModel && defaultModel) {
      setSelectedModel(defaultModel);
    }
  }, [conversationId, conversationModel, defaultModel]);

  const currentModel = selectedModel ?? conversationModel ?? defaultModel;

  const handleModelChange = (newModel: string) => {
    if (hasMessages) return;
    setSelectedModel(newModel);
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

  // ── File attachment ──────────────────────────────────────────────────────

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (!files.length) return;

    for (const file of files) {
      const localId = `local-${Date.now()}-${Math.random()}`;
      // Add a pending chip immediately
      setAttachments((prev) => [
        ...prev,
        { localId, filename: file.name, status: "uploading" },
      ]);

      // Upload in background — chip shows spinner until done
      documentService
        .upload(conversationId, file)
        .then((doc: Document) => {
          setAttachments((prev) =>
            prev.map((a) =>
              a.localId === localId ? { ...a, docId: doc.id, status: "ready" } : a
            )
          );
        })
        .catch((err: unknown) => {
          const msg =
            (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
            "Upload failed";
          setAttachments((prev) =>
            prev.map((a) =>
              a.localId === localId ? { ...a, status: "error", errorMsg: msg } : a
            )
          );
          toast.error(`${file.name}: ${msg}`);
        });
    }
  };

  const removeAttachment = (localId: string) => {
    setAttachments((prev) => prev.filter((a) => a.localId !== localId));
  };

  const isUploading = attachments.some((a) => a.status === "uploading");

  // ── Send ─────────────────────────────────────────────────────────────────

  const handleSendWithAttachments = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || disabled || isStreaming) return;

      const readyDocIds = attachments
        .filter((a) => a.status === "ready" && a.docId)
        .map((a) => a.docId!);

      onSend(trimmed, readyDocIds.length > 0 ? readyDocIds : undefined);
      setContent("");
      setAttachments([]);
      setShowSuggestions(false);
    },
    [attachments, disabled, isStreaming, onSend]
  );

  const handleSend = useCallback(() => {
    handleSendWithAttachments(content);
  }, [content, handleSendWithAttachments]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = content.trim().length > 0 && !disabled && !isStreaming && !isUploading;

  return (
    <div className="relative">
      {/* Suggested prompts */}
      <AnimatePresence>
        {showSuggestions && !content && attachments.length === 0 && (
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
          content || attachments.length > 0 || showSuggestions
            ? "border-brand-500/50 shadow-[0_0_0_1px_rgba(14,165,233,0.2)]"
            : "border-neutral-700",
          "p-2"
        )}
      >
        {/* ── Attachment chips — shown above textarea ── */}
        <AnimatePresence initial={false}>
          {attachments.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex flex-wrap gap-1.5 px-1 pb-2"
            >
              {attachments.map((att) => (
                <motion.div
                  key={att.localId}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border max-w-[200px]",
                    att.status === "ready"
                      ? "bg-neutral-700 border-neutral-600 text-neutral-200"
                      : att.status === "error"
                      ? "bg-red-500/10 border-red-500/30 text-red-400"
                      : "bg-neutral-800 border-neutral-700 text-neutral-400"
                  )}
                >
                  {att.status === "uploading" ? (
                    <Loader2 className="w-3 h-3 flex-shrink-0 animate-spin" />
                  ) : (
                    <FileText className="w-3 h-3 flex-shrink-0" />
                  )}
                  <span className="truncate">{att.filename}</span>
                  {att.status === "error" && (
                    <span className="text-red-400 text-[10px] flex-shrink-0">failed</span>
                  )}
                  <button
                    onClick={() => removeAttachment(att.localId)}
                    className="flex-shrink-0 rounded p-0.5 hover:bg-neutral-600 transition-colors"
                    title="Remove"
                  >
                    <X className="w-2.5 h-2.5" />
                  </button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Textarea row */}
        <div className="flex items-end gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,text/plain,text/markdown,application/pdf"
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming}
            className={cn(
              "flex-shrink-0 p-2 rounded-xl transition-colors",
              "text-neutral-500 hover:text-neutral-300 disabled:opacity-40"
            )}
            title="Attach file"
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
                  : isUploading
                  ? "Uploading files..."
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
            title={
              isUploading
                ? "Waiting for upload to finish..."
                : isStreaming
                ? "Stop generating"
                : "Send message"
            }
          >
            {isStreaming ? <Square className="w-3 h-3 fill-current" /> : <ArrowUp className="w-4 h-4" />}
          </button>
        </div>

        {/* Model selector / locked model row */}
        {models.length > 0 && (
          <div className="flex items-center gap-2 mt-1.5 px-1">
            {hasMessages ? (
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
