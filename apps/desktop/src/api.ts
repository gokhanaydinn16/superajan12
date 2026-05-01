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

const API_BASE = "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
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

export function runScan(limit: number) {
  return request<Record<string, unknown>>(`/scan?limit=${encodeURIComponent(limit)}`, { method: "POST" });
}

export function verifyEndpoints() {
  return request<Record<string, unknown>>("/verify-endpoints", { method: "POST" });
}
