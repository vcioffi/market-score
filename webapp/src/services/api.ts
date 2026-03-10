import type {
  LatestRunResponse,
  TickerAnalysis,
  TickersResponse,
  WeeklySummary,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }
  return response.json() as Promise<T>;
}

export async function getLatestRun(): Promise<LatestRunResponse> {
  return apiGet<LatestRunResponse>("/api/runs/latest");
}

export async function getWeeklySummaryLatest(): Promise<WeeklySummary> {
  return apiGet<WeeklySummary>("/api/weekly-summary/latest");
}

export async function getTickers(runDate?: string): Promise<TickersResponse> {
  const suffix = runDate ? `?run_date=${encodeURIComponent(runDate)}` : "";
  return apiGet<TickersResponse>(`/api/tickers${suffix}`);
}

export async function getTicker(symbol: string, runDate?: string): Promise<TickerAnalysis> {
  const suffix = runDate ? `?run_date=${encodeURIComponent(runDate)}` : "";
  return apiGet<TickerAnalysis>(`/api/ticker/${encodeURIComponent(symbol)}${suffix}`);
}
