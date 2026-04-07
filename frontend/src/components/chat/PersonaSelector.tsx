"use client";

import React from "react";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { useUpdateConversation } from "@/hooks/useConversations";
import toast from "react-hot-toast";

export interface PersonaOption {
  id: string;
  name: string;
  description: string;
  icon: string;
}

async function fetchPersonas(): Promise<{ personas: PersonaOption[]; default: string }> {
  const { data } = await apiClient.get("/health/personas");
  return data;
}

interface PersonaSelectorProps {
  conversationId: string;
  currentPersona: string;
  /** When true, renders as a compact grid for use in a header dropdown */
  compact?: boolean;
  /** Called after a persona is successfully selected (e.g. to close a dropdown) */
  onSelect?: () => void;
}

export function PersonaSelector({
  conversationId,
  currentPersona,
  compact = false,
  onSelect,
}: PersonaSelectorProps) {
  const { data } = useQuery({
    queryKey: ["personas"],
    queryFn: fetchPersonas,
    staleTime: Infinity,
  });

  const { mutate: updateConversation, isPending } = useUpdateConversation();

  const personas = data?.personas ?? [];
  if (personas.length === 0) return null;

  const handleSelect = (personaId: string) => {
    if (personaId === currentPersona || isPending) return;
    updateConversation(
      { id: conversationId, persona: personaId },
      {
        onSuccess: () => {
          const found = personas.find((p) => p.id === personaId);
          toast.success(`Switched to ${found?.name ?? personaId} mode`);
          onSelect?.();
        },
      }
    );
  };

  if (compact) {
    return (
      <div className="p-2 w-52">
        <p className="text-xs text-neutral-500 mb-2 px-1">Switch assistant mode</p>
        <div className="space-y-0.5">
          {personas.map((persona) => {
            const isActive = persona.id === currentPersona;
            return (
              <button
                key={persona.id}
                onClick={() => handleSelect(persona.id)}
                disabled={isPending}
                title={persona.description}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-all text-left",
                  "disabled:opacity-60 disabled:cursor-not-allowed",
                  isActive
                    ? "bg-brand-600/20 text-brand-300"
                    : "text-neutral-400 hover:bg-neutral-700 hover:text-neutral-200"
                )}
              >
                <span className="text-base leading-none">{persona.icon}</span>
                <div className="min-w-0">
                  <p className="font-medium leading-tight">{persona.name}</p>
                  <p className="text-xs text-neutral-500 truncate">{persona.description}</p>
                </div>
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-400 flex-shrink-0" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      <p className="text-xs text-neutral-500 mb-3 text-center">Choose an assistant mode</p>
      <div className="grid grid-cols-3 gap-2 max-w-sm mx-auto">
        {personas.map((persona) => {
          const isActive = persona.id === currentPersona;
          return (
            <motion.button
              key={persona.id}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => handleSelect(persona.id)}
              disabled={isPending}
              title={persona.description}
              className={cn(
                "flex flex-col items-center gap-1.5 p-3 rounded-xl border text-center transition-all",
                "disabled:opacity-60 disabled:cursor-not-allowed",
                isActive
                  ? "bg-brand-600/20 border-brand-500/50 text-brand-300"
                  : "bg-neutral-800/60 border-neutral-700 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 hover:border-neutral-600"
              )}
            >
              <span className="text-xl leading-none">{persona.icon}</span>
              <span className="text-xs font-medium leading-tight">{persona.name}</span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
