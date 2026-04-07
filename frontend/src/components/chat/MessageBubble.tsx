"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Check, Copy, ThumbsDown, ThumbsUp, Pencil, RotateCcw, X, Calculator, Cloud, Search, Wrench } from "lucide-react";
import { cn, copyToClipboard, formatChatTime } from "@/lib/utils";
import { MarkdownRenderer } from "@/components/shared/MarkdownRenderer";
import { useSubmitFeedback } from "@/hooks/useConversations";
import type { Message } from "@/types/api";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  isEditing?: boolean;
  onRegenerate?: () => void;
  onEditStart?: () => void;
  onEditCancel?: () => void;
  onEditSave?: (content: string) => void;
}

export function MessageBubble({
  message,
  isStreaming = false,
  isEditing = false,
  onRegenerate,
  onEditStart,
  onEditCancel,
  onEditSave,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const [hovering, setHovering] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<1 | -1 | null>(null);
  const [editContent, setEditContent] = useState(message.content);
  const editRef = useRef<HTMLTextAreaElement>(null);
  const { mutate: submitFeedback } = useSubmitFeedback();

  const isUser = message.role === "user";

  // Auto-resize edit textarea
  useEffect(() => {
    if (isEditing && editRef.current) {
      editRef.current.style.height = "auto";
      editRef.current.style.height = `${editRef.current.scrollHeight}px`;
      editRef.current.focus();
      editRef.current.setSelectionRange(editContent.length, editContent.length);
    }
  }, [isEditing]);

  const handleCopy = async () => {
    const ok = await copyToClipboard(message.content);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleFeedback = (rating: 1 | -1) => {
    setFeedbackGiven(rating);
    submitFeedback({ messageId: message.id, rating });
  };

  const handleEditSave = () => {
    const trimmed = editContent.trim();
    if (trimmed && trimmed !== message.content) {
      onEditSave?.(trimmed);
    } else {
      onEditCancel?.();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "group flex gap-3 px-4 py-3 rounded-xl",
        isUser ? "flex-row-reverse ml-8 sm:ml-12" : "mr-8 sm:mr-12"
      )}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-medium mt-0.5",
          isUser
            ? "bg-brand-600 text-white"
            : "bg-neutral-700 text-neutral-200"
        )}
      >
        {isUser ? "U" : "L"}
      </div>

      {/* Content */}
      <div className={cn("flex-1 min-w-0", isUser && "flex flex-col items-end")}>
        {isUser ? (
          isEditing ? (
            /* Inline edit mode */
            <div className="w-full max-w-[85%]">
              <textarea
                ref={editRef}
                value={editContent}
                onChange={(e) => {
                  setEditContent(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleEditSave();
                  }
                  if (e.key === "Escape") onEditCancel?.();
                }}
                className="w-full bg-neutral-800 border border-brand-500/50 rounded-xl px-4 py-2.5 text-sm text-neutral-100 outline-none resize-none leading-relaxed"
                rows={1}
              />
              <div className="flex items-center gap-2 mt-2 justify-end">
                <button
                  onClick={onEditCancel}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs text-neutral-400 hover:bg-neutral-800 transition-colors"
                >
                  <X className="w-3 h-3" /> Cancel
                </button>
                <button
                  onClick={handleEditSave}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs bg-brand-600 hover:bg-brand-500 text-white transition-colors"
                >
                  <Check className="w-3 h-3" /> Send
                </button>
              </div>
            </div>
          ) : (
            <div
              className={cn(
                "bg-brand-600/20 border border-brand-500/30 rounded-2xl rounded-tr-sm px-4 py-2.5",
                "text-neutral-100 text-sm leading-relaxed max-w-[85%]",
                message.is_edited && "opacity-90"
              )}
            >
              <p className="whitespace-pre-wrap break-words">{message.content}</p>
              {message.is_edited && (
                <span className="text-xs text-neutral-400 mt-1 block">(edited)</span>
              )}
            </div>
          )
        ) : (
          /* Assistant messages: full markdown */
          <div className="text-sm leading-relaxed">
            <MarkdownRenderer content={message.content} />
            {isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-brand-400 animate-pulse ml-0.5 rounded-sm" />
            )}
            {/* Tools used badges — shown on finished messages */}
            <ToolsBadges metadata={message.metadata} />
          </div>
        )}

        {/* Timestamp */}
        {!isEditing && (
          <span className="text-xs text-neutral-500 mt-1 px-1">
            {formatChatTime(message.created_at)}
          </span>
        )}

        {/* Action bar — appears on hover */}
        {hovering && !isStreaming && !isEditing && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn(
              "flex items-center gap-1 mt-1",
              isUser ? "flex-row-reverse" : "flex-row"
            )}
          >
            <ActionButton onClick={handleCopy} title="Copy">
              {copied ? (
                <Check className="w-3.5 h-3.5 text-green-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </ActionButton>

            {!isUser && (
              <>
                <ActionButton
                  onClick={() => handleFeedback(1)}
                  title="Good response"
                  active={feedbackGiven === 1}
                >
                  <ThumbsUp className="w-3.5 h-3.5" />
                </ActionButton>
                <ActionButton
                  onClick={() => handleFeedback(-1)}
                  title="Bad response"
                  active={feedbackGiven === -1}
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                </ActionButton>
                {onRegenerate && (
                  <ActionButton onClick={onRegenerate} title="Regenerate response">
                    <RotateCcw className="w-3.5 h-3.5" />
                  </ActionButton>
                )}
              </>
            )}

            {isUser && onEditStart && (
              <ActionButton onClick={onEditStart} title="Edit message">
                <Pencil className="w-3.5 h-3.5" />
              </ActionButton>
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}

const TOOL_ICONS: Record<string, React.ElementType> = {
  calculator: Calculator,
  get_weather: Cloud,
  web_search: Search,
};
const TOOL_LABELS: Record<string, string> = {
  calculator: "Calculator",
  get_weather: "Weather",
  web_search: "Web Search",
};

function ToolsBadges({ metadata }: { metadata: Record<string, unknown> }) {
  const toolsUsed = metadata?.tools_used as Array<{ name: string; is_error: boolean }> | undefined;
  if (!toolsUsed || toolsUsed.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {toolsUsed.map((t, i) => {
        const Icon = TOOL_ICONS[t.name] ?? Wrench;
        return (
          <span
            key={i}
            className={cn(
              "inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border",
              t.is_error
                ? "text-red-400 bg-red-500/10 border-red-500/20"
                : "text-neutral-400 bg-neutral-800 border-neutral-700"
            )}
          >
            <Icon className="w-3 h-3" />
            {TOOL_LABELS[t.name] ?? t.name}
          </span>
        );
      })}
    </div>
  );
}

function ActionButton({
  onClick,
  title,
  active,
  children,
}: {
  onClick: () => void;
  title: string;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        "p-1.5 rounded-md text-neutral-400 transition-colors",
        "hover:bg-neutral-700 hover:text-neutral-200",
        active && "text-brand-400 bg-brand-500/10"
      )}
    >
      {children}
    </button>
  );
}
