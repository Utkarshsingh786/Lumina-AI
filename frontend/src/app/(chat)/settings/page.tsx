"use client";

import React, { useState } from "react";
import {
  User,
  Brain,
  Cpu,
  LogOut,
  ChevronRight,
  Shield,
  Sparkles,
  Menu,
  Server,
  Globe,
  CheckCircle2,
  XCircle,
  Zap,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { useChatStore } from "@/store/chat";
import { useMemory } from "@/hooks/useMemory";
import { MemoryPanel } from "@/components/memory/MemoryPanel";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import type { ModelsResponse } from "@/types/api";

async function fetchModels(): Promise<ModelsResponse> {
  const { data } = await apiClient.get("/health/models");
  return data;
}

const PROVIDER_ICONS: Record<string, React.ElementType> = {
  openai: Brain,
  anthropic: Cpu,
  groq: Zap,
  gemini: Sparkles,
  ollama: Server,
  openrouter: Globe,
};

const PROVIDER_SETUP: Record<string, string> = {
  openai: "Set OPENAI_API_KEY in backend/.env",
  anthropic: "Set ANTHROPIC_API_KEY in backend/.env",
  groq: "Set GROQ_API_KEY in backend/.env (free at console.groq.com)",
  gemini: "Set GEMINI_API_KEY in backend/.env (free at aistudio.google.com)",
  ollama: "Set OLLAMA_ENABLED=true and run: ollama serve",
  openrouter: "Set OPENROUTER_API_KEY in backend/.env (free at openrouter.ai)",
};

export default function SettingsPage() {
  const { user, logout } = useAuthStore();
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);
  const [showMemoryPanel, setShowMemoryPanel] = useState(false);
  const { data: memories } = useMemory();
  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: fetchModels,
    staleTime: 60_000,
  });

  if (!user) return null;

  const initials = (user.full_name ?? user.username)
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const providers = modelsData?.providers ?? {};
  const freeModels = (modelsData?.models ?? []).filter((m) => m.is_free);
  const paidModels = (modelsData?.models ?? []).filter((m) => !m.is_free);

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-neutral-950 scrollbar-thin scrollbar-thumb-neutral-800">
      {/* Mobile header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-neutral-800 md:hidden">
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-sm font-semibold text-neutral-200">Settings</h1>
      </div>

      <div className="max-w-2xl mx-auto w-full px-4 py-8 space-y-6">
        {/* Page title — desktop */}
        <div className="hidden md:block">
          <h1 className="text-xl font-semibold text-neutral-100">Settings</h1>
          <p className="text-sm text-neutral-500 mt-1">Manage your account and preferences</p>
        </div>

        {/* ── Profile ─────────────────────────────────── */}
        <Section title="Profile" icon={<User className="w-4 h-4" />}>
          <div className="flex items-center gap-4 p-4">
            <div className="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center text-white font-semibold text-lg flex-shrink-0">
              {initials}
            </div>
            <div className="min-w-0">
              <p className="font-medium text-neutral-100 truncate">
                {user.full_name ?? user.username}
              </p>
              <p className="text-sm text-neutral-400 truncate">{user.email}</p>
              <span
                className={cn(
                  "inline-block mt-1 text-xs px-2 py-0.5 rounded-full border",
                  user.role === "admin"
                    ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
                    : "text-neutral-500 bg-neutral-800 border-neutral-700"
                )}
              >
                {user.role}
              </span>
            </div>
          </div>
          <Divider />
          <InfoRow label="Username" value={`@${user.username}`} />
          <InfoRow label="Email" value={user.email} />
          <InfoRow label="Account status" value={user.is_active ? "Active" : "Inactive"} />
        </Section>

        {/* ── AI Providers ─────────────────────────────── */}
        <Section title="AI Providers" icon={<Cpu className="w-4 h-4" />}>
          <div className="px-4 py-2">
            <p className="text-xs text-neutral-500 mb-3">
              Configure providers in <code className="text-brand-400 bg-brand-500/10 px-1 rounded">backend/.env</code>
            </p>
            <div className="space-y-2">
              {Object.entries(providers).map(([key, p]) => {
                const Icon = PROVIDER_ICONS[key] ?? Cpu;
                return (
                  <div key={key} className="flex items-start gap-3 py-2">
                    <Icon className="w-4 h-4 text-neutral-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-neutral-200">{p.label}</span>
                        {p.configured ? (
                          <span className="flex items-center gap-1 text-xs text-emerald-400">
                            <CheckCircle2 className="w-3 h-3" /> Connected
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-neutral-600">
                            <XCircle className="w-3 h-3" /> Not configured
                          </span>
                        )}
                      </div>
                      {!p.configured && (
                        <p className="text-xs text-neutral-600 mt-0.5">{PROVIDER_SETUP[key]}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Section>

        {/* ── Available Models ─────────────────────────── */}
        <Section title="Available Models" icon={<Zap className="w-4 h-4" />}>
          {modelsData?.models.length === 0 ? (
            <div className="px-4 py-4 text-sm text-neutral-500">No models configured yet.</div>
          ) : (
            <>
              {freeModels.length > 0 && (
                <div className="px-4 py-3">
                  <p className="text-xs font-medium text-emerald-400 mb-2 flex items-center gap-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/20">FREE</span>
                    Free models — no cost
                  </p>
                  <div className="space-y-1">
                    {freeModels.map((m) => (
                      <div key={m.id} className="flex items-center justify-between py-1">
                        <div>
                          <span className="text-sm text-neutral-300">{m.name}</span>
                          <span className="text-xs text-neutral-600 ml-2">{m.description}</span>
                        </div>
                        <span className="text-xs text-neutral-600 capitalize">{m.provider}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {freeModels.length > 0 && paidModels.length > 0 && <Divider />}
              {paidModels.length > 0 && (
                <div className="px-4 py-3">
                  <p className="text-xs font-medium text-neutral-500 mb-2">Paid models</p>
                  <div className="space-y-1">
                    {paidModels.map((m) => (
                      <div key={m.id} className="flex items-center justify-between py-1">
                        <div>
                          <span className="text-sm text-neutral-300">{m.name}</span>
                          <span className="text-xs text-neutral-600 ml-2">{m.description}</span>
                        </div>
                        <span className="text-xs text-neutral-600 capitalize">{m.provider}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          <Divider />
          <div className="px-4 py-3">
            <p className="text-xs text-neutral-500 leading-relaxed">
              Switch model per-conversation using the selector in the chat input.
              To use free models, set <code className="text-brand-400 bg-brand-500/10 px-1 rounded">OPENROUTER_API_KEY</code> (free at{" "}
              <span className="text-brand-400">openrouter.ai</span>) or run Ollama locally with{" "}
              <code className="text-brand-400 bg-brand-500/10 px-1 rounded">OLLAMA_ENABLED=true</code>.
            </p>
          </div>
        </Section>

        {/* ── Memory ──────────────────────────────────────────────────────── */}
        <Section title="Memory" icon={<Brain className="w-4 h-4" />}>
          <div className="px-4 py-3 flex items-center justify-between">
            <div>
              <p className="text-sm text-neutral-200">Stored memories</p>
              <p className="text-xs text-neutral-500 mt-0.5">
                {memories
                  ? `${memories.length} memor${memories.length === 1 ? "y" : "ies"} about you`
                  : "Loading…"}
              </p>
            </div>
            <button
              onClick={() => setShowMemoryPanel(true)}
              className="flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 transition-colors"
            >
              View all <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <Divider />
          <div className="px-4 py-3">
            <p className="text-xs text-neutral-500 leading-relaxed">
              Lumina automatically extracts facts and preferences from your conversations.
              You can view, disable, or delete individual memories.
            </p>
          </div>
        </Section>

        {/* ── Security ────────────────────────────────────────────────────── */}
        <Section title="Security" icon={<Shield className="w-4 h-4" />}>
          <InfoRow label="Session" value="JWT (15 min access token, 7 day refresh)" subtle />
          <InfoRow label="Rate limiting" value="30 chat messages / minute" subtle />
        </Section>

        {/* ── About ───────────────────────────────────────────────────────── */}
        <Section title="About" icon={<Sparkles className="w-4 h-4" />}>
          <InfoRow label="Version" value="0.1.0" />
          <InfoRow label="Stack" value="Next.js 15 + FastAPI + PostgreSQL + Redis" subtle />
        </Section>

        {/* ── Account ─────────────────────────────────────────────────────── */}
        <div className="pb-8">
          <button
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 transition-colors text-sm font-medium"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </div>

      {/* Memory panel overlay */}
      {showMemoryPanel && (
        <div className="fixed inset-0 z-50 flex">
          <div className="flex-1 bg-black/60" onClick={() => setShowMemoryPanel(false)} />
          <div className="w-80 h-full relative">
            <MemoryPanel onClose={() => setShowMemoryPanel(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-neutral-800">
        <span className="text-neutral-500">{icon}</span>
        <h2 className="text-sm font-medium text-neutral-300">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function InfoRow({ label, value, subtle = false }: { label: string; value: string; subtle?: boolean }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 gap-4">
      <span className="text-sm text-neutral-400 flex-shrink-0">{label}</span>
      <span className={cn("text-sm text-right truncate", subtle ? "text-neutral-600" : "text-neutral-200")}>
        {value}
      </span>
    </div>
  );
}

function Divider() {
  return <div className="border-t border-neutral-800/60 mx-4" />;
}
