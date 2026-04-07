"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart2,
  Zap,
  DollarSign,
  Activity,
  Clock,
  Menu,
  TrendingUp,
  Cpu,
  MessageSquare,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useChatStore } from "@/store/chat";
import { cn } from "@/lib/utils";
import type { UsageSummary, UsageTimelinePoint, UsageByModel } from "@/types/api";

// ── Fetchers ───────────────────────────────────────────
const fetchSummary = async (days: number): Promise<UsageSummary> =>
  (await apiClient.get(`/usage/summary?days=${days}`)).data;
const fetchTimeline = async (days: number): Promise<{ timeline: UsageTimelinePoint[] }> =>
  (await apiClient.get(`/usage/timeline?days=${days}`)).data;
const fetchByModel = async (days: number): Promise<{ models: UsageByModel[] }> =>
  (await apiClient.get(`/usage/by-model?days=${days}`)).data;

// ── Formatters ─────────────────────────────────────────
const fmtTokens = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
};
const fmtCost = (n: number) => {
  if (n === 0) return "$0.00";
  if (n < 0.0001) return `<$0.0001`;
  if (n < 0.01) return `$${n.toFixed(5)}`;
  return `$${n.toFixed(4)}`;
};
const fmtMs = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${Math.round(n)}ms`);
const fmtDate = (s: string) => {
  const d = new Date(s + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

const PERIODS = [
  { label: "7d", value: 7 },
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
];

// ── Bar chart ──────────────────────────────────────────
// Heights are pixel-based so zero bars are always visible (never sub-pixel).
const CHART_H = 96;   // px — total bar area height
const MIN_BAR = 4;    // px — minimum height for days WITH data
const ZERO_BAR = 2;   // px — height for days with zero activity

function BarChart({
  data,
  valueKey,
  color = "brand",
}: {
  data: UsageTimelinePoint[];
  valueKey: "tokens" | "cost_usd" | "requests";
  color?: "brand" | "emerald" | "violet";
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const values = data.map((d) => Number(d[valueKey]) || 0);
  const max = Math.max(...values, 0);
  const hasData = max > 0;

  const activeBar: Record<typeof color, string> = {
    brand:   "bg-brand-500",
    emerald: "bg-emerald-500",
    violet:  "bg-violet-500",
  };
  const activeBarHover: Record<typeof color, string> = {
    brand:   "bg-brand-400",
    emerald: "bg-emerald-400",
    violet:  "bg-violet-400",
  };

  const formatVal = (d: UsageTimelinePoint) =>
    valueKey === "tokens"
      ? `${fmtTokens(Number(d.tokens))} tokens`
      : valueKey === "cost_usd"
      ? fmtCost(Number(d.cost_usd))
      : `${d.requests} requests`;

  return (
    <div>
      {/* Chart area */}
      <div
        className="relative flex items-end gap-px"
        style={{ height: `${CHART_H}px` }}
      >
        {/* Baseline rule */}
        <div className="absolute bottom-0 inset-x-0 h-px bg-neutral-700/60" />

        {data.map((d, i) => {
          const val = values[i];
          const barPx =
            val === 0
              ? ZERO_BAR
              : Math.max(Math.round((val / max) * CHART_H), MIN_BAR);
          const isHovered = hovered === i;
          const isToday = i === data.length - 1;

          return (
            <div
              key={d.date}
              className="relative flex-1 flex items-end cursor-default"
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
            >
              {/* Bar */}
              <div
                className={cn(
                  "w-full rounded-t-sm transition-colors duration-75",
                  val === 0
                    ? isHovered
                      ? "bg-neutral-700"
                      : "bg-neutral-800"
                    : isHovered
                    ? activeBarHover[color]
                    : isToday
                    ? activeBar[color]
                    : activeBar[color] + " opacity-75"
                )}
                style={{ height: `${barPx}px` }}
              />

              {/* Tooltip — rendered inside bar container, not clipped by parent overflow */}
              {isHovered && (
                <div
                  className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 z-20 pointer-events-none"
                  style={{ whiteSpace: "nowrap" }}
                >
                  <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-xs text-neutral-200 shadow-xl">
                    <p className="font-medium text-neutral-400 mb-0.5">
                      {fmtDate(d.date)}{isToday ? " · today" : ""}
                    </p>
                    <p className="font-semibold">{formatVal(d)}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* X-axis labels */}
      <div className="flex items-center justify-between mt-2 text-[10px] text-neutral-600 select-none">
        <span>{fmtDate(data[0]?.date ?? "")}</span>
        {data.length > 6 && (
          <span>{fmtDate(data[Math.floor(data.length / 2)]?.date ?? "")}</span>
        )}
        <span className="text-neutral-500">today</span>
      </div>

      {/* No-data overlay */}
      {!hasData && (
        <p className="text-center text-xs text-neutral-600 mt-2">
          No activity in this period — bars show when you start chatting
        </p>
      )}
    </div>
  );
}

// ── Stat card ──────────────────────────────────────────
function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  accent?: "emerald" | "amber" | "brand";
}) {
  const accentColor = {
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    brand: "text-brand-400",
  };
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
      <div className="flex items-center gap-2 mb-2.5 text-neutral-500">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <p
        className={cn(
          "text-2xl font-bold tracking-tight",
          accent ? accentColor[accent] : "text-neutral-100"
        )}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-neutral-600 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Section wrapper ────────────────────────────────────
function Section({
  title,
  icon,
  children,
  badge,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  badge?: string;
}) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-neutral-800">
        {icon && <span className="text-neutral-500">{icon}</span>}
        <h2 className="text-sm font-semibold text-neutral-200 flex-1">{title}</h2>
        {badge && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-neutral-800 text-neutral-500">
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

// ── Provider badge ─────────────────────────────────────
function ProviderBadge({ provider }: { provider: string }) {
  const colors: Record<string, string> = {
    openai: "bg-emerald-500/10 text-emerald-400",
    anthropic: "bg-amber-500/10 text-amber-400",
    ollama: "bg-blue-500/10 text-blue-400",
    openrouter: "bg-violet-500/10 text-violet-400",
    groq: "bg-orange-500/10 text-orange-400",
    gemini: "bg-sky-500/10 text-sky-400",
  };
  return (
    <span
      className={cn(
        "text-[10px] px-1.5 py-0.5 rounded font-medium capitalize",
        colors[provider] ?? "bg-neutral-700 text-neutral-400"
      )}
    >
      {provider}
    </span>
  );
}

// ── Main page ──────────────────────────────────────────
export default function UsagePage() {
  const [days, setDays] = useState(30);
  const [chartTab, setChartTab] = useState<"tokens" | "cost_usd" | "requests">("tokens");
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);

  const { data: summary, isLoading: sumLoading } = useQuery({
    queryKey: ["usage-summary", days],
    queryFn: () => fetchSummary(days),
    staleTime: 60_000,
  });
  const { data: timelineData, isLoading: tlLoading } = useQuery({
    queryKey: ["usage-timeline", days],
    queryFn: () => fetchTimeline(days),
    staleTime: 60_000,
  });
  const { data: byModelData, isLoading: modelLoading } = useQuery({
    queryKey: ["usage-by-model", days],
    queryFn: () => fetchByModel(days),
    staleTime: 60_000,
  });

  const timeline = timelineData?.timeline ?? [];
  const models = byModelData?.models ?? [];
  const hasActivity = (summary?.total_requests ?? 0) > 0;

  // Derived stats
  const tokensPerReq =
    summary && summary.total_requests > 0
      ? Math.round(summary.total_tokens / summary.total_requests)
      : 0;
  const costPerReq =
    summary && summary.total_requests > 0
      ? summary.total_cost_usd / summary.total_requests
      : 0;
  const peakDay = timeline.reduce(
    (best, d) => (d.tokens > (best?.tokens ?? 0) ? d : best),
    null as UsageTimelinePoint | null
  );
  const maxModelTokens = models[0]?.total_tokens ?? 0;

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
        <h1 className="text-sm font-semibold text-neutral-200">Usage & Cost</h1>
      </div>

      <div className="max-w-4xl mx-auto w-full px-4 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-neutral-100">Usage & Cost</h1>
            <p className="text-sm text-neutral-500 mt-0.5">
              Token consumption, spending, and model performance
            </p>
          </div>
          {/* Period selector */}
          <div className="flex items-center gap-1 bg-neutral-800 rounded-lg p-1 flex-shrink-0">
            {PERIODS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setDays(opt.value)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  days === opt.value
                    ? "bg-neutral-700 text-neutral-100 shadow-sm"
                    : "text-neutral-500 hover:text-neutral-300"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Primary stat cards ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard
            icon={<Zap className="w-4 h-4" />}
            label="Total tokens"
            value={sumLoading ? "…" : fmtTokens(summary?.total_tokens ?? 0)}
            sub={
              sumLoading
                ? ""
                : `${fmtTokens(summary?.total_prompt_tokens ?? 0)} in · ${fmtTokens(summary?.total_completion_tokens ?? 0)} out`
            }
            accent="brand"
          />
          <StatCard
            icon={<DollarSign className="w-4 h-4" />}
            label="Total spend"
            value={sumLoading ? "…" : fmtCost(summary?.total_cost_usd ?? 0)}
            sub={
              hasActivity && (summary?.total_cost_usd ?? 0) === 0
                ? "Free models only"
                : "USD"
            }
            accent={hasActivity && (summary?.total_cost_usd ?? 0) > 0 ? "amber" : "emerald"}
          />
          <StatCard
            icon={<Activity className="w-4 h-4" />}
            label="Requests"
            value={sumLoading ? "…" : fmtTokens(summary?.total_requests ?? 0)}
            sub={`last ${days} days`}
          />
          <StatCard
            icon={<Clock className="w-4 h-4" />}
            label="Avg latency"
            value={sumLoading ? "…" : fmtMs(summary?.avg_latency_ms ?? 0)}
            sub="per request"
          />
        </div>

        {/* ── Secondary derived stats ── */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <StatCard
            icon={<TrendingUp className="w-4 h-4" />}
            label="Tokens / request"
            value={sumLoading ? "…" : hasActivity ? fmtTokens(tokensPerReq) : "—"}
            sub="avg per call"
          />
          <StatCard
            icon={<DollarSign className="w-4 h-4" />}
            label="Cost / request"
            value={sumLoading ? "…" : hasActivity ? fmtCost(costPerReq) : "—"}
            sub="avg per call"
          />
          <StatCard
            icon={<Sparkles className="w-4 h-4" />}
            label="Peak day"
            value={
              sumLoading || tlLoading
                ? "…"
                : peakDay && peakDay.tokens > 0
                ? fmtDate(peakDay.date)
                : "—"
            }
            sub={
              peakDay && peakDay.tokens > 0
                ? `${fmtTokens(peakDay.tokens)} tokens`
                : "no activity yet"
            }
          />
        </div>

        {/* ── Daily activity chart ── */}
        <Section
          title="Daily activity"
          icon={<BarChart2 className="w-4 h-4" />}
          badge={`${days + 1} days`}
        >
          {/* Chart tabs */}
          <div className="flex items-center gap-1 px-4 pt-3">
            {(
              [
                { key: "tokens", label: "Tokens" },
                { key: "cost_usd", label: "Cost" },
                { key: "requests", label: "Requests" },
              ] as const
            ).map((t) => (
              <button
                key={t.key}
                onClick={() => setChartTab(t.key)}
                className={cn(
                  "px-3 py-1 rounded-lg text-xs font-medium transition-colors",
                  chartTab === t.key
                    ? "bg-neutral-700 text-neutral-200"
                    : "text-neutral-500 hover:text-neutral-300"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="px-4 pb-4 pt-3">
            {tlLoading ? (
              <div className="h-20 flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <BarChart
                data={timeline}
                valueKey={chartTab}
                color={
                  chartTab === "tokens"
                    ? "brand"
                    : chartTab === "cost_usd"
                    ? "emerald"
                    : "violet"
                }
              />
            )}
          </div>
        </Section>

        {/* ── Model breakdown ── */}
        {!modelLoading && models.length > 0 ? (
          <Section
            title="Usage by model"
            icon={<Cpu className="w-4 h-4" />}
            badge={`${models.length} model${models.length !== 1 ? "s" : ""}`}
          >
            <div className="divide-y divide-neutral-800/50">
              {models.map((m) => {
                const pct =
                  maxModelTokens > 0 ? (m.total_tokens / maxModelTokens) * 100 : 0;
                const isFree = m.total_cost_usd === 0;
                return (
                  <div key={`${m.provider}-${m.model}`} className="px-4 py-3.5">
                    {/* Row 1: name + cost */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-sm font-medium text-neutral-200 truncate flex-1">
                        {m.model}
                      </span>
                      <ProviderBadge provider={m.provider} />
                      <span
                        className={cn(
                          "text-sm font-semibold flex-shrink-0",
                          isFree ? "text-emerald-400" : "text-neutral-300"
                        )}
                      >
                        {isFree ? "FREE" : fmtCost(m.total_cost_usd)}
                      </span>
                    </div>

                    {/* Progress bar */}
                    <div className="w-full h-1.5 bg-neutral-800 rounded-full mb-2">
                      <div
                        className="h-full bg-brand-500 rounded-full transition-all"
                        style={{ width: `${Math.max(pct, 1)}%` }}
                      />
                    </div>

                    {/* Row 2: stats */}
                    <div className="flex items-center gap-4 text-xs text-neutral-500">
                      <span className="flex items-center gap-1">
                        <Zap className="w-3 h-3" />
                        {fmtTokens(m.total_tokens)} tokens
                      </span>
                      <span className="text-neutral-700">·</span>
                      <span>{fmtTokens(m.prompt_tokens)} in</span>
                      <span className="text-neutral-700">·</span>
                      <span>{fmtTokens(m.completion_tokens)} out</span>
                      <span className="text-neutral-700">·</span>
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" />
                        {m.requests} req
                      </span>
                      <span className="text-neutral-700">·</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {fmtMs(m.avg_latency_ms)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer totals */}
            <div className="px-4 py-3 border-t border-neutral-800 bg-neutral-900/40 flex items-center justify-between text-xs text-neutral-500">
              <span>
                {models.length} model{models.length !== 1 ? "s" : ""} ·{" "}
                {models.reduce((a, m) => a + m.requests, 0)} total requests
              </span>
              <span className="font-medium text-neutral-400">
                {fmtTokens(models.reduce((a, m) => a + m.total_tokens, 0))} tokens total
              </span>
            </div>
          </Section>
        ) : !modelLoading && !hasActivity ? (
          /* ── Empty state ── */
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 px-6 py-14 text-center">
            <div className="w-12 h-12 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mx-auto mb-4">
              <Sparkles className="w-6 h-6 text-brand-400" />
            </div>
            <h3 className="text-sm font-semibold text-neutral-200 mb-1">No usage yet</h3>
            <p className="text-xs text-neutral-500 max-w-xs mx-auto">
              Start a conversation to see your token usage, cost, and model performance here.
            </p>
            <a
              href="/"
              className="inline-flex items-center gap-1.5 mt-4 text-xs text-brand-400 hover:text-brand-300 transition-colors"
            >
              Start chatting <ChevronRight className="w-3 h-3" />
            </a>
          </div>
        ) : null}
      </div>
    </div>
  );
}
