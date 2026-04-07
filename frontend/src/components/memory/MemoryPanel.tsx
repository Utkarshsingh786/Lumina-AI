"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, Trash2, EyeOff, Eye, X, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useMemory, useDeleteMemory, useToggleMemory } from "@/hooks/useMemory";
import type { MemoryEntry, MemoryType } from "@/types/api";

const TYPE_LABELS: Record<MemoryType, { label: string; color: string }> = {
  fact: { label: "Fact", color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
  preference: { label: "Preference", color: "text-purple-400 bg-purple-500/10 border-purple-500/20" },
  instruction: { label: "Instruction", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
  context: { label: "Context", color: "text-teal-400 bg-teal-500/10 border-teal-500/20" },
};

interface MemoryPanelProps {
  onClose: () => void;
}

export function MemoryPanel({ onClose }: MemoryPanelProps) {
  const [showInactive, setShowInactive] = useState(false);
  const { data: memories, isLoading } = useMemory(showInactive);
  const { mutate: deleteMemory, isPending: isDeleting } = useDeleteMemory();
  const { mutate: toggleMemory } = useToggleMemory();

  // Group by type
  const grouped = (memories ?? []).reduce<Record<string, MemoryEntry[]>>((acc, m) => {
    (acc[m.memory_type] ??= []).push(m);
    return acc;
  }, {});

  const typeOrder: MemoryType[] = ["instruction", "preference", "fact", "context"];
  const sortedTypes = typeOrder.filter((t) => grouped[t]?.length > 0);

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ type: "spring", stiffness: 400, damping: 35 }}
      className="absolute inset-0 z-30 flex flex-col bg-neutral-900 border-r border-neutral-800"
    >
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-brand-400" />
          <span className="text-sm font-medium text-neutral-200">Memories</span>
          {memories && memories.length > 0 && (
            <span className="text-xs text-neutral-500 tabular-nums">({memories.length})</span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-neutral-800 text-neutral-500 hover:text-neutral-300 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 border-b border-neutral-800/50">
        <p className="text-xs text-neutral-500">Things Lumina remembers about you</p>
        <button
          onClick={() => setShowInactive(!showInactive)}
          className={cn(
            "flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors",
            showInactive
              ? "text-neutral-300 bg-neutral-800"
              : "text-neutral-500 hover:text-neutral-400"
          )}
        >
          {showInactive ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          {showInactive ? "Showing all" : "Show disabled"}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-neutral-800 px-3 py-3 space-y-4">
        {isLoading ? (
          <MemorySkeleton />
        ) : memories?.length === 0 ? (
          <EmptyMemory />
        ) : (
          sortedTypes.map((type) => (
            <MemoryGroup
              key={type}
              type={type}
              entries={grouped[type]}
              onDelete={(id) => deleteMemory(id)}
              onToggle={(id, isActive) => toggleMemory({ id, isActive })}
              isDeleting={isDeleting}
            />
          ))
        )}
      </div>
    </motion.div>
  );
}

function MemoryGroup({
  type,
  entries,
  onDelete,
  onToggle,
  isDeleting,
}: {
  type: MemoryType;
  entries: MemoryEntry[];
  onDelete: (id: string) => void;
  onToggle: (id: string, isActive: boolean) => void;
  isDeleting: boolean;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const meta = TYPE_LABELS[type];

  return (
    <div>
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-1 mb-1.5 group"
      >
        <span className={cn("text-xs font-medium px-1.5 py-0.5 rounded border", meta.color)}>
          {meta.label}
        </span>
        <span className="text-xs text-neutral-600">{entries.length}</span>
        <span className="ml-auto text-neutral-600 group-hover:text-neutral-400 transition-colors">
          {collapsed ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden space-y-1"
          >
            {entries.map((entry) => (
              <MemoryCard
                key={entry.id}
                entry={entry}
                onDelete={onDelete}
                onToggle={onToggle}
                isDeleting={isDeleting}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MemoryCard({
  entry,
  onDelete,
  onToggle,
  isDeleting,
}: {
  entry: MemoryEntry;
  onDelete: (id: string) => void;
  onToggle: (id: string, isActive: boolean) => void;
  isDeleting: boolean;
}) {
  return (
    <div
      className={cn(
        "group flex items-start gap-2 px-3 py-2 rounded-lg border transition-all",
        entry.is_active
          ? "bg-neutral-800/60 border-neutral-700/50"
          : "bg-neutral-800/20 border-neutral-800 opacity-50"
      )}
    >
      <p className="flex-1 text-xs text-neutral-300 leading-relaxed">{entry.content}</p>
      <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={() => onToggle(entry.id, !entry.is_active)}
          title={entry.is_active ? "Disable memory" : "Enable memory"}
          className="p-1 rounded hover:bg-neutral-700 text-neutral-500 hover:text-neutral-300 transition-colors"
        >
          {entry.is_active ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
        </button>
        <button
          onClick={() => {
            if (confirm("Delete this memory?")) onDelete(entry.id);
          }}
          disabled={isDeleting}
          title="Delete memory"
          className="p-1 rounded hover:bg-red-500/10 text-neutral-500 hover:text-red-400 transition-colors disabled:opacity-50"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

function EmptyMemory() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Brain className="w-8 h-8 text-neutral-700 mb-3" />
      <p className="text-sm text-neutral-500">No memories yet</p>
      <p className="text-xs text-neutral-600 mt-1 max-w-[180px]">
        Lumina will automatically remember important things from your conversations.
      </p>
    </div>
  );
}

function MemorySkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-10 bg-neutral-800 rounded-lg" />
      ))}
    </div>
  );
}
