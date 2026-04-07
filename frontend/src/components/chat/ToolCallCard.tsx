"use client";

import React from "react";
import { motion } from "framer-motion";
import { Calculator, Cloud, Search, Wrench, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ActiveToolCall } from "@/types/api";

// Map tool names to display labels and icons
const TOOL_META: Record<string, { label: string; Icon: React.ElementType }> = {
  calculator: { label: "Calculator", Icon: Calculator },
  get_weather: { label: "Weather", Icon: Cloud },
  web_search: { label: "Web Search", Icon: Search },
};

function getToolMeta(toolName: string) {
  return TOOL_META[toolName] ?? { label: toolName, Icon: Wrench };
}

interface ToolCallCardProps {
  toolCall: ActiveToolCall;
}

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const { label, Icon } = getToolMeta(toolCall.tool_name);
  const isRunning = toolCall.status === "running";
  const isError = toolCall.status === "error";
  const isDone = toolCall.status === "done";

  // Build a short human-readable summary of the inputs
  const inputSummary = Object.entries(toolCall.input)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(" · ");

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "flex items-start gap-3 px-4 py-2.5 rounded-xl border text-sm",
        "bg-neutral-800/60 border-neutral-700/60 my-1",
        isError && "border-red-500/30 bg-red-950/20",
        isDone && "border-green-500/20 bg-green-950/10",
      )}
    >
      {/* Tool icon */}
      <div
        className={cn(
          "w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center mt-0.5",
          isRunning && "bg-brand-600/20",
          isDone && "bg-green-600/15",
          isError && "bg-red-600/15",
        )}
      >
        <Icon
          className={cn(
            "w-3.5 h-3.5",
            isRunning && "text-brand-400",
            isDone && "text-green-400",
            isError && "text-red-400",
          )}
        />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-neutral-200">{label}</span>
          {inputSummary && (
            <span className="text-neutral-400 truncate max-w-[200px]">{inputSummary}</span>
          )}

          {/* Status indicator */}
          <div className="ml-auto flex-shrink-0">
            {isRunning && (
              <Loader2 className="w-3.5 h-3.5 text-brand-400 animate-spin" />
            )}
            {isDone && (
              <CheckCircle className="w-3.5 h-3.5 text-green-400" />
            )}
            {isError && (
              <XCircle className="w-3.5 h-3.5 text-red-400" />
            )}
          </div>
        </div>

        {/* Result (only show when done or error) */}
        {(isDone || isError) && toolCall.result && (
          <p
            className={cn(
              "mt-1 text-xs leading-relaxed",
              isError ? "text-red-400" : "text-neutral-400",
            )}
          >
            {toolCall.result}
          </p>
        )}
      </div>
    </motion.div>
  );
}
