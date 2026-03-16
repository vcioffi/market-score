import type {
  LatestRunResponse,
  LiveNews,
  LiveQuote,
  MacroAnalysis,
  TickerAnalysis,
  TickersResponse,
  WeeklySummary,
} from "../types/api";

// In dev mode the Vite proxy forwards /api/* to the backend, so we use a relative base.
// In production builds set VITE_API_BASE_URL to point at the backend host.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

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

export async function getMacroLatest(runDate?: string): Promise<MacroAnalysis> {
  const suffix = runDate ? `?run_date=${encodeURIComponent(runDate)}` : "";
  return apiGet<MacroAnalysis>(`/api/macro/latest${suffix}`);
}

export async function getLiveQuote(symbol: string, period = "3mo"): Promise<LiveQuote> {
  return apiGet<LiveQuote>(
    `/api/live/quote/${encodeURIComponent(symbol)}?period=${encodeURIComponent(period)}`,
  );
}

export async function getLiveNews(symbol: string, limit = 15): Promise<LiveNews> {
  return apiGet<LiveNews>(
    `/api/live/news/${encodeURIComponent(symbol)}?limit=${limit}`,
  );
}
