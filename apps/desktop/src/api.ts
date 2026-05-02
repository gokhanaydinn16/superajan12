import { invoke } from "@tauri-apps/api/core";

export type SourceHealth = {
  name: string;
  status: string;
  last_ok_at: string | null;
  last_error_at: string | null;
  latency_ms: number | null;
  stale_after_seconds: number;
  error: string | null;
  metadata: Record<string, unknown>;
};

export type DashboardPayload = {
  aggregate: Record<string, number | string | null>;
  latest: Record<string, number | string | null> | null;
  top_markets: Array<Record<string, number | string | null>>;
  shadow: Record<string, number | string | null>;
  mode: string;
  live_trading: string;
};

export type BackendEvent = {
  id: string;
  type: string;
  created_at: string;
  payload: Record<string, unknown>;
};

export type DesktopBackendStatus = {
  running: boolean;
  url: string;
  ws_url: string;
  mode: string;
  message: string | null;
};

export type ResearchTasksPayload = {
  tasks: Array<Record<string, unknown>>;
  providers: Array<Record<string, unknown>>;
};

export type MarketsPayload = {
  top_markets: Array<Record<string, unknown>>;
  latest_scan: Record<string, unknown> | null;
  source_health_mode: string;
  market_summary: Record<string, unknown>;
  source_summary: Record<string, number>;
  reference_sources: Array<Record<string, unknown>>;
};

export type WalletEventsPayload = {
  events: Array<Record<string, unknown>>;
  providers: Array<Record<string, unknown>>;
  status: string;
};

export type StrategyScoresPayload = {
  scores: Array<Record<string, unknown>>;
  models: Array<Record<string, unknown>>;
  live_eligible_models: Array<Record<string, unknown>>;
  promotion_checks: Array<Record<string, unknown>>;
  model_history: Array<Record<string, unknown>>;
  summary: Record<string, unknown>;
  last_transition: Record<string, unknown> | null;
};

export type RiskStatusPayload = {
  mode: string;
  safety: Record<string, unknown>;
  capital: Record<string, unknown>;
  execution: Record<string, unknown>;
  aggregate: Record<string, unknown>;
  risk_signals: Record<string, Record<string, unknown>>;
  source_health_gate: Record<string, unknown>;
};

export type PositionsPayload = {
  positions: Array<Record<string, unknown>>;
  shadow: Record<string, unknown>;
};

export type AuditEventsPayload = {
  events: Array<Record<string, unknown>>;
};

export type ExecutionStatusPayload = {
  mode: string;
  live_trading: string;
  approval: Record<string, unknown>;
  secrets: {
    ready: boolean;
    required: Array<Record<string, unknown>>;
  };
  reconciliation: Record<string, unknown>;
  guard: Record<string, unknown>;
  dry_run_order_supported: boolean;
  dry_run_preview: Record<string, unknown> | null;
};

export type SystemHealthPayload = {
  ok: boolean;
  uptime_seconds: number;
  mode: string;
  backend: Record<string, unknown>;
  database: Record<string, unknown>;
  audit_log: Record<string, unknown>;
  sources: Record<string, unknown>;
};

export type StrategyTransitionPayload = {
  status: "candidate" | "shadow" | "approved" | "retired";
  notes?: string;
  model_name?: string;
  model_version?: string;
  changed_by?: string;
};

const FALLBACK_STATUS: DesktopBackendStatus = {
  running: false,
  url: "http://127.0.0.1:8000",
  ws_url: "ws://127.0.0.1:8000",
  mode: "external",
  message: "desktop sidecar unavailable; using default local backend",
};

let backendStatusPromise: Promise<DesktopBackendStatus> | null = null;

function isTauriRuntime() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function resolveBackendStatus() {
  if (!isTauriRuntime()) return FALLBACK_STATUS;
  try {
    return await invoke<DesktopBackendStatus>("desktop_backend_status");
  } catch (error) {
    return {
      ...FALLBACK_STATUS,
      message: `desktop sidecar status unavailable: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

async function getBackendStatus() {
  backendStatusPromise ??= resolveBackendStatus();
  return backendStatusPromise;
}

async function refreshBackendStatus() {
  backendStatusPromise = resolveBackendStatus();
  return backendStatusPromise;
}

export async function getDesktopBackendStatus() {
  return getBackendStatus();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let backend = await getBackendStatus();
  let response: Response;

  try {
    response = await fetch(`${backend.url}${path}`, init);
  } catch {
    backend = await refreshBackendStatus();
    response = await fetch(`${backend.url}${path}`, init);
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<Record<string, unknown>>("/health");
}

export function getSources() {
  return request<{ sources: SourceHealth[] }>("/sources");
}

export function getDashboard() {
  return request<DashboardPayload>("/dashboard");
}

export function getEvents(limit = 100) {
  return request<{ events: BackendEvent[] }>(`/events?limit=${encodeURIComponent(limit)}`);
}

export function getResearchTasks() {
  return request<ResearchTasksPayload>("/research/tasks");
}

export function getMarkets() {
  return request<MarketsPayload>("/markets");
}

export function getWalletEvents() {
  return request<WalletEventsPayload>("/wallet/events");
}

export function getStrategyScores() {
  return request<StrategyScoresPayload>("/strategy/scores");
}

export function getRiskStatus() {
  return request<RiskStatusPayload>("/risk/status");
}

export function getPositions() {
  return request<PositionsPayload>("/positions");
}

export function getExecutionStatus() {
  return request<ExecutionStatusPayload>("/execution/status");
}

export function getSystemHealth() {
  return request<SystemHealthPayload>("/system/health");
}

export function getAuditEvents(limit = 100) {
  return request<AuditEventsPayload>(`/audit/events?limit=${encodeURIComponent(limit)}`);
}

export async function connectEventStream(onEvent: (event: BackendEvent) => void, onError: (message: string) => void) {
  const backend = await getBackendStatus();
  const socket = new WebSocket(`${backend.ws_url}/events/stream`);
  socket.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as BackendEvent);
    } catch (error) {
      onError(`event parse failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  };
  socket.onerror = () => onError("event stream error");
  socket.onclose = () => onError("event stream closed");
  return socket;
}

export function runScan(limit: number) {
  return request<Record<string, unknown>>(`/scan?limit=${encodeURIComponent(limit)}`, { method: "POST" });
}

export function verifyEndpoints() {
  return request<Record<string, unknown>>("/verify-endpoints", { method: "POST" });
}

export function transitionStrategyModel(payload: StrategyTransitionPayload) {
  return request<Record<string, unknown>>("/strategy/models/transition", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function enableSafeMode(reason: string) {
  return request<Record<string, unknown>>(`/safety/enable-safe-mode?reason=${encodeURIComponent(reason)}`, { method: "POST" });
}

export function enableKillSwitch(reason: string) {
  return request<Record<string, unknown>>(`/safety/enable-kill-switch?reason=${encodeURIComponent(reason)}`, { method: "POST" });
}

export function clearSafety() {
  return request<Record<string, unknown>>("/safety/clear", { method: "POST" });
}
