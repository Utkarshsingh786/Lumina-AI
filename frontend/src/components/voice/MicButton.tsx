"use client";

import { Mic, MicOff, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface MicButtonProps {
  /** Current state from useVoice */
  recordState: "idle" | "recording" | "processing";
  onClick: () => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Mic button with three visual states:
 *  idle       → grey mic icon
 *  recording  → pulsing red mic icon (indicates live recording)
 *  processing → spinner (waiting for transcription)
 */
export function MicButton({ recordState, onClick, disabled, className }: MicButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || recordState === "processing"}
      title={
        recordState === "recording"
          ? "Click to stop recording"
          : recordState === "processing"
          ? "Transcribing…"
          : "Click to record voice input"
      }
      className={cn(
        "p-2 rounded-lg transition-all duration-150",
        recordState === "idle" &&
          "text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800",
        recordState === "recording" &&
          "text-red-400 bg-red-500/15 hover:bg-red-500/25 animate-pulse",
        recordState === "processing" &&
          "text-neutral-600 cursor-not-allowed",
        className
      )}
    >
      {recordState === "processing" ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : recordState === "recording" ? (
        <MicOff className="w-4 h-4" />
      ) : (
        <Mic className="w-4 h-4" />
      )}
    </button>
  );
}
