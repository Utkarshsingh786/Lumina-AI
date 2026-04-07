/**
 * API type definitions — matches backend Pydantic schemas exactly.
 * Single source of truth for all API shapes used by services and hooks.
 */

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  avatar_url: string | null;
  role: string;
  is_active: boolean;
  settings: Record<string, unknown>;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Conversation {
  id: string;
  title: string;
  model: string;
  persona: string;
  is_pinned: boolean;
  is_archived: boolean;
  is_public: boolean;
  share_token: string | null;
  token_count: number;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationListItem {
  id: string;
  title: string;
  model: string;
  persona: string;
  is_pinned: boolean;
  is_archived: boolean;
  is_public: boolean;
  share_token: string | null;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  content_type: string;
  token_count: number | null;
  is_edited: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface APIError {
  error_code: string;
  message: string;
  details: Record<string, unknown>;
}

// ── SSE Event Types ────────────────────────────────────
export type SSEEventType = "token" | "done" | "error" | "close" | "tool_use" | "tool_result";

export interface SSETokenEvent {
  type: "token";
  content: string;
}

export interface SSEDoneEvent {
  type: "done";
  message_id: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    latency_ms: number;
    tools_used?: Array<{ name: string; is_error: boolean }>;
  };
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
}

export interface SSEToolUseEvent {
  type: "tool_use";
  tool_name: string;
  input: Record<string, unknown>;
}

export interface SSEToolResultEvent {
  type: "tool_result";
  tool_name: string;
  result: string;
  is_error: boolean;
}

export type SSEEvent =
  | SSETokenEvent
  | SSEDoneEvent
  | SSEErrorEvent
  | SSEToolUseEvent
  | SSEToolResultEvent;

// ── Document / RAG Types ───────────────────────────────
export type DocumentStatus = "pending" | "indexing" | "ready" | "error";

export interface Document {
  id: string;
  conversation_id: string | null;
  filename: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
}

// ── Memory Types ───────────────────────────────────────
export type MemoryType = "fact" | "preference" | "instruction" | "context";

export interface MemoryEntry {
  id: string;
  content: string;
  memory_type: MemoryType;
  importance: number;
  is_active: boolean;
  conversation_id: string | null;
  created_at: string;
  expires_at: string | null;
  metadata: Record<string, unknown>;
}

// ── Model / Provider Types ─────────────────────────────────
export interface ModelOption {
  id: string;
  name: string;
  provider: string;
  tier: "best" | "fast" | "embedding";
  is_free: boolean;
  context_window: number;
  description: string;
  supports_tools: boolean;
}

export interface ProviderStatus {
  configured: boolean;
  label: string;
}

export interface ModelsResponse {
  models: ModelOption[];
  default: string;
  providers: Record<string, ProviderStatus>;
}

// ── Tool call display types ────────────────────────────
export interface ActiveToolCall {
  tool_name: string;
  input: Record<string, unknown>;
  status: "running" | "done" | "error";
  result?: string;
}

// ── Usage / Cost Analytics ─────────────────────────────
export interface UsageSummary {
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_usd: number;
  total_requests: number;
  avg_latency_ms: number;
  period_days: number;
  period_start: string;
  period_end: string;
}

export interface UsageTimelinePoint {
  date: string;
  tokens: number;
  cost_usd: number;
  requests: number;
}

export interface UsageByModel {
  model: string;
  provider: string;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost_usd: number;
  requests: number;
  avg_latency_ms: number;
}

// ── Admin ──────────────────────────────────────────────
export interface AdminStats {
  users: { total: number; active: number; new_24h: number };
  conversations: { total: number; new_24h: number };
  messages: { total: number };
  documents: { total: number };
}

// ── Agent Workflows ────────────────────────────────────
export interface AgentWorkflow {
  id: string;
  name: string;
  description: string;
  icon: string;
  steps: number;
  step_names: string[];
}

export type AgentSSEEventType =
  | "step_start"
  | "token"
  | "step_done"
  | "done"
  | "error"
  | "tool_use"
  | "tool_result";

export interface AgentStepStartEvent {
  type: "step_start";
  step: number;
  name: string;
  total_steps: number;
}

export interface AgentStepDoneEvent {
  type: "step_done";
  step: number;
  name: string;
  tokens: number;
}

export interface AgentRunCreatedEvent {
  type: "run_created";
  run_id: string;
}

export interface AgentDoneEvent {
  type: "done";
  run_id: string;
  steps_completed: number;
  total_tokens: number;
}

export type AgentSSEEvent =
  | AgentRunCreatedEvent
  | AgentStepStartEvent
  | AgentStepDoneEvent
  | AgentDoneEvent
  | SSETokenEvent
  | SSEErrorEvent
  | SSEToolUseEvent
  | SSEToolResultEvent;

// ── Workflow run history ───────────────────────────────
export interface WorkflowRunSummary {
  id: string;
  workflow_id: string;
  workflow_name: string;
  workflow_icon: string;
  input_preview: string;
  model: string;
  status: "running" | "completed" | "failed" | "cancelled";
  total_tokens: number;
  steps_completed: number;
  created_at: string;
  completed_at: string | null;
  error: string | null;
}

export interface WorkflowStepResult {
  step: number;
  name: string;
  content: string;
  tokens: number;
}

export interface WorkflowRunDetail extends Omit<WorkflowRunSummary, "input_preview"> {
  input: string;
  step_results: WorkflowStepResult[];
}

// ── Organisations ──────────────────────────────────────
export interface OrgMember {
  user_id: string;
  username: string;
  email: string;
  full_name: string | null;
  role: "owner" | "admin" | "member";
  joined_at: string;
}

export interface Organization {
  id: string;
  name: string;
  description: string | null;
  invite_token: string | null;
  invite_expires_at: string | null;
  member_count: number;
  created_at: string;
}

export interface OrganizationDetail extends Organization {
  members: OrgMember[];
}
