"use client";

import React, { useRef, useState, useEffect } from "react";
import { ChevronDown, Zap, Brain, Cpu, Server, Globe, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ModelOption } from "@/types/api";

// Re-export so MessageInput can import from one place
export type { ModelOption };

const PROVIDER_META: Record<string, { label: string; Icon: React.ElementType; color: string }> = {
  openai:      { label: "OpenAI",          Icon: Brain,  color: "text-emerald-400" },
  anthropic:   { label: "Anthropic",       Icon: Cpu,    color: "text-purple-400" },
  ollama:      { label: "Ollama (local)",  Icon: Server, color: "text-orange-400" },
  openrouter:  { label: "OpenRouter",      Icon: Globe,  color: "text-sky-400" },
};

interface ModelSelectorProps {
  models: ModelOption[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}

export function ModelSelector({ models, value, onChange, disabled = false }: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = models.find((m) => m.id === value) ?? models[0];

  // Group models by provider
  const grouped = models.reduce<Record<string, ModelOption[]>>((acc, m) => {
    (acc[m.provider] ??= []).push(m);
    return acc;
  }, {});
  const providerOrder = ["openai", "anthropic", "openrouter", "ollama"];
  const sortedProviders = [
    ...providerOrder.filter((p) => grouped[p]),
    ...Object.keys(grouped).filter((p) => !providerOrder.includes(p)),
  ];

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (!selected) return null;

  const ProviderIcon = PROVIDER_META[selected.provider]?.Icon ?? Brain;
  const providerColor = PROVIDER_META[selected.provider]?.color ?? "text-neutral-400";

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger */}
      <button
        onClick={() => !disabled && setOpen((v) => !v)}
        disabled={disabled}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium",
          "bg-neutral-800 border border-neutral-700 text-neutral-300",
          "hover:bg-neutral-700 hover:text-neutral-100 hover:border-neutral-600",
          "transition-colors outline-none",
          open && "bg-neutral-700 border-neutral-600",
          disabled && "opacity-50 cursor-not-allowed pointer-events-none",
        )}
        aria-label="Select model"
      >
        <ProviderIcon className={cn("w-3 h-3 flex-shrink-0", providerColor)} />
        <span className="max-w-[140px] truncate">{selected.name}</span>
        {selected.is_free && (
          <span className="text-[10px] px-1 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 leading-none">
            FREE
          </span>
        )}
        <ChevronDown className={cn("w-3 h-3 text-neutral-500 transition-transform", open && "rotate-180")} />
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.97 }}
            transition={{ duration: 0.12 }}
            className={cn(
              "absolute bottom-full mb-1.5 left-0 z-50",
              "w-72 bg-neutral-800 border border-neutral-700 rounded-xl shadow-2xl overflow-hidden",
            )}
          >
            <div className="max-h-[360px] overflow-y-auto scrollbar-thin p-1.5 space-y-2">
              {sortedProviders.map((provider) => {
                const meta = PROVIDER_META[provider] ?? { label: provider, Icon: Cpu, color: "text-neutral-400" };
                return (
                  <div key={provider}>
                    {/* Provider heading */}
                    <div className="flex items-center gap-1.5 px-2 py-1">
                      <meta.Icon className={cn("w-3 h-3", meta.color)} />
                      <span className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                        {meta.label}
                      </span>
                    </div>
                    {/* Models in this group */}
                    <div className="space-y-0.5">
                      {grouped[provider].map((model) => (
                        <ModelItem
                          key={model.id}
                          model={model}
                          isSelected={model.id === value}
                          onSelect={() => { onChange(model.id); setOpen(false); }}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ModelItem({
  model,
  isSelected,
  onSelect,
}: {
  model: ModelOption;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const TierIcon = model.tier === "fast" ? Zap : Brain;

  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full flex items-start gap-2.5 px-2.5 py-2 rounded-lg text-left transition-colors",
        isSelected
          ? "bg-brand-600/20 text-brand-200"
          : "text-neutral-200 hover:bg-neutral-700",
      )}
    >
      <TierIcon className={cn("w-3.5 h-3.5 flex-shrink-0 mt-0.5", isSelected ? "text-brand-400" : "text-neutral-500")} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-sm font-medium truncate">{model.name}</span>
          {model.is_free && (
            <span className="text-[10px] px-1 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 leading-none flex-shrink-0">
              FREE
            </span>
          )}
          {!model.supports_tools && (
            <span className="text-[10px] px-1 py-0.5 rounded bg-neutral-700 text-neutral-500 border border-neutral-600 leading-none flex-shrink-0">
              no tools
            </span>
          )}
        </div>
        {model.description && (
          <p className="text-xs text-neutral-500 mt-0.5 line-clamp-1">{model.description}</p>
        )}
      </div>
      {isSelected && <Check className="w-3.5 h-3.5 text-brand-400 flex-shrink-0 mt-0.5" />}
    </button>
  );
}
