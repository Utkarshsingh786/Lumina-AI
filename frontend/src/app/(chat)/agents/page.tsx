"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Play,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Menu,
  ArrowLeft,
  ChevronDown,
  History,
  Trash2,
  RotateCcw,
  Clock,
  Zap,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { getStoredAccessToken } from "@/lib/api";
import { useChatStore } from "@/store/chat";
import { MarkdownRenderer } from "@/components/shared/MarkdownRenderer";
import { cn } from "@/lib/utils";
import type {
  AgentWorkflow,
  AgentSSEEvent,
  WorkflowRunSummary,
  WorkflowRunDetail,
} from "@/types/api";

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  is_free: boolean;
}

interface WorkflowsResponse {
  workflows: AgentWorkflow[];
  models: ModelOption[];
  default_model: string;
}

const fetchWorkflows = async (): Promise<WorkflowsResponse> =>
  (await apiClient.get("/agents/workflows")).data;

const fetchRuns = async (page: number): Promise<{ runs: WorkflowRunSummary[]; total: number; pages: number }> =>
  (await apiClient.get(`/agents/runs?page=${page}&page_size=20`)).data;

const fetchRunDetail = async (runId: string): Promise<WorkflowRunDetail> =>
  (await apiClient.get(`/agents/runs/${runId}`)).data;

// ── Status badge ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: WorkflowRunSummary["status"] }) {
  const map = {
    running:   { cls: "bg-blue-500/10 text-blue-400 border-blue-500/20",    label: "Running" },
    completed: { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", label: "Done" },
    failed:    { cls: "bg-red-500/10 text-red-400 border-red-500/20",       label: "Failed" },
    cancelled: { cls: "bg-neutral-500/10 text-neutral-400 border-neutral-700", label: "Cancelled" },
  };
  const { cls, label } = map[status] ?? map.cancelled;
  return (
    <span className={cn("text-[10px] px-1.5 py-0.5 rounded border font-medium", cls)}>
      {label}
    </span>
  );
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── Step output (used in both live run and history detail) ──────────────────

interface StepState {
  name: string;
  status: "pending" | "running" | "done";
  content: string;
  tokens: number;
}

function StepCard({ step, index }: { step: StepState; index: number }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-xl border border-neutral-800 overflow-hidden">
      <button
        onClick={() => step.status !== "running" && setOpen((v) => !v)}
        className={cn(
          "w-full flex items-center gap-3 px-4 py-2.5 border-b border-neutral-800 text-left transition-colors",
          step.status === "running" ? "bg-brand-500/5" : "bg-neutral-900/40 hover:bg-neutral-900/70"
        )}
      >
        {step.status === "running" ? (
          <Loader2 className="w-4 h-4 text-brand-400 animate-spin flex-shrink-0" />
        ) : step.status === "done" ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
        ) : (
          <div className="w-4 h-4 rounded-full border border-neutral-700 flex-shrink-0" />
        )}
        <span className="text-sm font-medium text-neutral-200 flex-1">
          Step {index + 1}: {step.name}
        </span>
        {step.status === "done" && step.tokens > 0 && (
          <span className="text-xs text-neutral-600 flex items-center gap-1">
            <Zap className="w-3 h-3" />{step.tokens}
          </span>
        )}
        {step.status !== "running" && step.content && (
          <ChevronDown className={cn("w-3.5 h-3.5 text-neutral-600 transition-transform", !open && "-rotate-90")} />
        )}
      </button>
      {open && step.content && (
        <div className="px-4 py-3 text-sm text-neutral-300">
          <MarkdownRenderer content={step.content} />
        </div>
      )}
    </div>
  );
}

// ── History panel ───────────────────────────────────────────────────────────

function HistoryPanel({
  onRunAgain,
  onViewRun,
  selectedRunId,
}: {
  onRunAgain: (run: WorkflowRunSummary) => void;
  onViewRun: (run: WorkflowRunSummary) => void;
  selectedRunId: string | null;
}) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["agent-runs", page],
    queryFn: () => fetchRuns(page),
    staleTime: 30_000,
  });

  const runs = data?.runs ?? [];
  const pages = data?.pages ?? 1;

  const handleDelete = async (runId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleting(runId);
    try {
      await apiClient.delete(`/agents/runs/${runId}`);
      queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
    } finally {
      setDeleting(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-5 h-5 text-neutral-600 animate-spin" />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <History className="w-8 h-8 text-neutral-700 mb-3" />
        <p className="text-sm text-neutral-500">No runs yet</p>
        <p className="text-xs text-neutral-600 mt-1">Run a workflow to see your history here</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {runs.map((run) => (
          <div
            key={run.id}
            role="button"
            tabIndex={0}
            onClick={() => onViewRun(run)}
            onKeyDown={(e) => e.key === "Enter" && onViewRun(run)}
            className={cn(
              "w-full text-left px-3 py-2.5 rounded-xl border transition-colors group cursor-pointer",
              selectedRunId === run.id
                ? "bg-brand-500/10 border-brand-500/20"
                : "hover:bg-neutral-800 border-transparent"
            )}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-base">{run.workflow_icon}</span>
              <span className="text-xs font-medium text-neutral-300 flex-1 truncate">{run.workflow_name}</span>
              <StatusBadge status={run.status} />
            </div>
            <p className="text-xs text-neutral-500 truncate pl-6">{run.input_preview}</p>
            <div className="flex items-center gap-2 mt-1.5 pl-6">
              <span className="text-[10px] text-neutral-600 flex items-center gap-1">
                <Clock className="w-2.5 h-2.5" />{timeAgo(run.created_at)}
              </span>
              {run.total_tokens > 0 && (
                <span className="text-[10px] text-neutral-600 flex items-center gap-1">
                  <Zap className="w-2.5 h-2.5" />{run.total_tokens.toLocaleString()} tokens
                </span>
              )}
              <div className="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => { e.stopPropagation(); onRunAgain(run); }}
                  title="Run again"
                  className="p-1 rounded hover:bg-neutral-700 text-neutral-500 hover:text-neutral-300 transition-colors"
                >
                  <RotateCcw className="w-3 h-3" />
                </button>
                <button
                  onClick={(e) => handleDelete(run.id, e)}
                  title="Delete run"
                  className="p-1 rounded hover:bg-red-500/10 text-neutral-500 hover:text-red-400 transition-colors"
                  disabled={deleting === run.id}
                >
                  {deleting === run.id
                    ? <Loader2 className="w-3 h-3 animate-spin" />
                    : <Trash2 className="w-3 h-3" />
                  }
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {pages > 1 && (
        <div className="flex-shrink-0 flex items-center justify-center gap-2 p-2 border-t border-neutral-800">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 text-neutral-400 transition-colors"
          >
            Prev
          </button>
          <span className="text-xs text-neutral-600">{page} / {pages}</span>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page >= pages}
            className="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 text-neutral-400 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// ── Run detail view (history) ───────────────────────────────────────────────

function RunDetailView({
  run,
  onBack,
  onRunAgain,
}: {
  run: WorkflowRunSummary;
  onBack: () => void;
  onRunAgain: (run: WorkflowRunSummary) => void;
}) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ["agent-run-detail", run.id],
    queryFn: () => fetchRunDetail(run.id),
    staleTime: Infinity,
  });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-neutral-800 flex-shrink-0">
        <button onClick={onBack} className="p-1.5 rounded text-neutral-500 hover:text-neutral-200 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <span className="text-xl">{run.workflow_icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-neutral-100">{run.workflow_name}</h2>
            <StatusBadge status={run.status} />
          </div>
          <p className="text-xs text-neutral-500">{timeAgo(run.created_at)} · {run.model}</p>
        </div>
        <button
          onClick={() => onRunAgain(run)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 border border-brand-500/20 transition-colors"
        >
          <RotateCcw className="w-3 h-3" /> Run again
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Input */}
        <div className="rounded-xl border border-neutral-800 p-4">
          <p className="text-xs text-neutral-500 mb-2 font-medium uppercase tracking-wide">Input</p>
          <p className="text-sm text-neutral-300 whitespace-pre-wrap">{detail?.input ?? run.input_preview}</p>
        </div>

        {/* Error */}
        {run.error && (
          <div className="flex items-start gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{run.error}</span>
          </div>
        )}

        {/* Steps */}
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-5 h-5 text-neutral-600 animate-spin" />
          </div>
        ) : (
          detail?.step_results.map((sr, i) => (
            <StepCard
              key={i}
              index={i}
              step={{ name: sr.name, status: "done", content: sr.content, tokens: sr.tokens }}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);
  const queryClient = useQueryClient();

  // Left panel tab
  const [leftTab, setLeftTab] = useState<"workflows" | "history">("workflows");

  // Workflow selector
  const [selected, setSelected] = useState<AgentWorkflow | null>(null);
  const [input, setInput] = useState("");

  // Model selector
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const modelDropdownRef = useRef<HTMLDivElement>(null);

  // Right panel mode: "run" (live) | "detail" (history view)
  const [rightMode, setRightMode] = useState<"run" | "detail">("run");
  const [viewingRun, setViewingRun] = useState<WorkflowRunSummary | null>(null);

  // Live run state
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<StepState[]>([]);
  const [currentStep, setCurrentStep] = useState(-1);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);

  const outputRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const currentStepRef = useRef(-1);

  const { data } = useQuery({
    queryKey: ["agent-workflows"],
    queryFn: fetchWorkflows,
    staleTime: Infinity,
  });
  const workflows = data?.workflows ?? [];
  const models = data?.models ?? [];

  useEffect(() => {
    if (data?.default_model && !selectedModel) setSelectedModel(data.default_model);
  }, [data?.default_model]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(e.target as Node))
        setShowModelDropdown(false);
    };
    if (showModelDropdown) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showModelDropdown]);

  useEffect(() => {
    outputRef.current?.scrollTo({ top: outputRef.current.scrollHeight, behavior: "smooth" });
  }, [steps]);

  useEffect(() => { currentStepRef.current = currentStep; }, [currentStep]);

  const resetRun = () => {
    setSteps([]);
    setCurrentStep(-1);
    setDone(false);
    setError(null);
    setLiveRunId(null);
  };

  const runWorkflow = async () => {
    if (!selected || !input.trim() || running) return;
    resetRun();
    setRightMode("run");
    setRunning(true);

    const token = getStoredAccessToken();
    const base = process.env.NEXT_PUBLIC_API_URL || "";
    const controller = new AbortController();
    abortRef.current = controller;

    setSteps(selected.step_names.map((name) => ({ name, status: "pending", content: "", tokens: 0 })));

    try {
      const response = await fetch(`${base}/api/v1/agents/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          workflow_id: selected.id,
          input: input.trim(),
          model: selectedModel || undefined,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.message || `Request failed: ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const block of events) {
          const line = block.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          try {
            const event = JSON.parse(raw) as AgentSSEEvent;

            if (event.type === "run_created") {
              setLiveRunId(event.run_id);
            } else if (event.type === "step_start") {
              setCurrentStep(event.step);
              currentStepRef.current = event.step;
              setSteps((prev) =>
                prev.map((s, i) => (i === event.step ? { ...s, status: "running" } : s))
              );
            } else if (event.type === "token") {
              const idx = currentStepRef.current;
              setSteps((prev) =>
                prev.map((s, i) => (i === idx ? { ...s, content: s.content + event.content } : s))
              );
            } else if (event.type === "step_done") {
              setSteps((prev) =>
                prev.map((s, i) =>
                  i === event.step ? { ...s, status: "done", tokens: event.tokens } : s
                )
              );
            } else if (event.type === "done") {
              setDone(true);
              // Refresh history list so the new run appears immediately
              queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
            } else if (event.type === "error") {
              setError(event.message);
              queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== "AbortError") {
        setError((e as Error).message || "Workflow failed");
      }
    } finally {
      setRunning(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  const handleViewRun = (run: WorkflowRunSummary) => {
    setViewingRun(run);
    setRightMode("detail");
  };

  const handleRunAgain = (run: WorkflowRunSummary) => {
    // Find the workflow definition for this run
    const wf = workflows.find((w) => w.id === run.workflow_id);
    if (wf) setSelected(wf);
    // Pre-fill with the original input (preview might be truncated; detail will have full)
    // We set to the preview for now; if detail is cached, we'll prefer that
    const cachedDetail = queryClient.getQueryData<WorkflowRunDetail>(["agent-run-detail", run.id]);
    setInput(cachedDetail?.input ?? run.input_preview);
    resetRun();
    setLeftTab("workflows");
    setRightMode("run");
  };

  const currentModelName = models.find((m) => m.id === selectedModel)?.name ?? selectedModel;

  const showRightPanel = selected || rightMode === "detail";

  return (
    <div className="flex flex-col h-full bg-neutral-950">
      {/* Mobile header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-neutral-800 md:hidden">
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h1 className="text-sm font-semibold text-neutral-200">Agents</h1>
      </div>

      <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
        {/* ── Left panel ── */}
        <div className={cn(
          "md:w-72 border-r border-neutral-800 flex flex-col overflow-hidden",
          showRightPanel && "hidden md:flex"
        )}>
          {/* Left panel header + tabs */}
          <div className="px-4 pt-4 pb-0 border-b border-neutral-800 flex-shrink-0">
            <h2 className="text-base font-semibold text-neutral-100 flex items-center gap-2 mb-3">
              <Bot className="w-4 h-4 text-brand-400" /> Agent Workflows
            </h2>
            <div className="flex gap-1">
              {(["workflows", "history"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setLeftTab(tab)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-t-lg border-b-2 transition-colors capitalize",
                    leftTab === tab
                      ? "text-neutral-100 border-brand-500"
                      : "text-neutral-500 border-transparent hover:text-neutral-300"
                  )}
                >
                  {tab === "history" && <History className="w-3 h-3" />}
                  {tab}
                </button>
              ))}
            </div>
          </div>

          {/* Workflows tab */}
          {leftTab === "workflows" && (
            <>
              <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {workflows.map((w) => (
                  <button
                    key={w.id}
                    onClick={() => { setSelected(w); resetRun(); setRightMode("run"); }}
                    className={cn(
                      "w-full text-left px-3 py-3 rounded-xl transition-colors",
                      selected?.id === w.id && rightMode === "run"
                        ? "bg-brand-500/10 border border-brand-500/20"
                        : "hover:bg-neutral-800 border border-transparent"
                    )}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{w.icon}</span>
                      <span className="text-sm font-medium text-neutral-200">{w.name}</span>
                    </div>
                    <p className="text-xs text-neutral-500 leading-relaxed pl-7">{w.description}</p>
                    <div className="flex flex-wrap items-center gap-1 mt-2 pl-7">
                      {w.step_names.map((s) => (
                        <span key={s} className="text-[10px] px-1.5 py-0.5 bg-neutral-800 text-neutral-500 rounded">
                          {s}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>

              {/* Model selector — bottom of workflows tab */}
              {models.length > 0 && (
                <div className="flex-shrink-0 border-t border-neutral-800 p-3">
                  <p className="text-xs text-neutral-600 mb-1.5">Model</p>
                  <div className="relative" ref={modelDropdownRef}>
                    <button
                      onClick={() => setShowModelDropdown((v) => !v)}
                      disabled={running}
                      className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-neutral-800 border border-neutral-700 hover:border-neutral-600 text-sm text-neutral-300 transition-colors disabled:opacity-50"
                    >
                      <span className="truncate text-xs">{currentModelName || "Select model"}</span>
                      <ChevronDown className="w-3 h-3 text-neutral-500 flex-shrink-0" />
                    </button>
                    {showModelDropdown && (
                      <div className="absolute bottom-full mb-1 left-0 right-0 z-20 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl max-h-60 overflow-y-auto">
                        {models.map((m) => (
                          <button
                            key={m.id}
                            onClick={() => { setSelectedModel(m.id); setShowModelDropdown(false); }}
                            className={cn(
                              "w-full flex items-center justify-between px-3 py-2 text-xs text-left hover:bg-neutral-700 transition-colors",
                              m.id === selectedModel && "bg-brand-500/10 text-brand-400"
                            )}
                          >
                            <span className="truncate">{m.name}</span>
                            <span className={cn(
                              "ml-2 flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded",
                              m.is_free ? "bg-emerald-500/10 text-emerald-400" : "bg-neutral-700 text-neutral-500"
                            )}>
                              {m.is_free ? "FREE" : m.provider}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* History tab */}
          {leftTab === "history" && (
            <HistoryPanel
              onRunAgain={handleRunAgain}
              onViewRun={handleViewRun}
              selectedRunId={viewingRun?.id ?? null}
            />
          )}
        </div>

        {/* ── Right panel ── */}
        <div className={cn(
          "flex-1 flex flex-col overflow-hidden",
          !showRightPanel && "hidden md:flex items-center justify-center"
        )}>
          {/* History detail view */}
          {rightMode === "detail" && viewingRun ? (
            <RunDetailView
              run={viewingRun}
              onBack={() => { setRightMode("run"); setViewingRun(null); }}
              onRunAgain={handleRunAgain}
            />
          ) : !selected ? (
            /* Empty state */
            <div className="text-center px-8">
              <Bot className="w-12 h-12 text-neutral-700 mx-auto mb-4" />
              <p className="text-sm text-neutral-500 mb-2">Select a workflow to get started</p>
              <button
                onClick={() => setLeftTab("history")}
                className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1 mx-auto"
              >
                <History className="w-3 h-3" /> View past runs
              </button>
            </div>
          ) : (
            /* Live run view */
            <>
              <div className="flex items-center gap-3 px-4 py-3 border-b border-neutral-800 flex-shrink-0">
                <button
                  onClick={() => { setSelected(null); resetRun(); }}
                  className="p-1.5 rounded text-neutral-500 hover:text-neutral-200 transition-colors md:hidden"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <span className="text-xl">{selected.icon}</span>
                <div className="flex-1 min-w-0">
                  <h2 className="text-sm font-semibold text-neutral-100">{selected.name}</h2>
                  <p className="text-xs text-neutral-500">
                    {selected.steps} steps · <span className="text-neutral-400">{currentModelName}</span>
                  </p>
                </div>
                {running && (
                  <button
                    onClick={stop}
                    className="text-xs px-3 py-1.5 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    Stop
                  </button>
                )}
              </div>

              {/* Input area — hidden once run starts */}
              {!running && steps.length === 0 && (
                <div className="p-4 border-b border-neutral-800 flex-shrink-0">
                  <p className="text-xs text-neutral-500 mb-2">{selected.description}</p>
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Enter your input for the workflow…"
                    rows={4}
                    className="w-full bg-neutral-800 border border-neutral-700 rounded-xl px-4 py-3 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-brand-500 resize-none"
                  />
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-xs text-neutral-600">
                      Model: <span className="text-neutral-400">{currentModelName}</span>
                    </span>
                    <button
                      onClick={runWorkflow}
                      disabled={!input.trim() || !selectedModel}
                      className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
                    >
                      <Play className="w-4 h-4" /> Run workflow
                    </button>
                  </div>
                </div>
              )}

              {/* Steps output */}
              <div
                ref={outputRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-neutral-800"
              >
                {error && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
                  </div>
                )}

                {steps.map((step, i) => (
                  <StepCard key={i} index={i} step={step} />
                ))}

                {done && (
                  <div className="flex flex-col items-center gap-3 py-4">
                    <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                    <p className="text-sm text-neutral-400">Workflow complete</p>
                    {liveRunId && (
                      <p className="text-xs text-neutral-600">Run saved to history</p>
                    )}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => { resetRun(); setInput(""); }}
                        className="text-xs px-4 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition-colors"
                      >
                        New run
                      </button>
                      <button
                        onClick={() => { setLeftTab("history"); }}
                        className="text-xs px-4 py-2 rounded-lg bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 border border-brand-500/20 transition-colors flex items-center gap-1"
                      >
                        <History className="w-3 h-3" /> View history
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
