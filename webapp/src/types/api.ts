export interface TickerLight {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  market: string;
  peers: string[];
  risk_score?: number;
  benefit_score?: number;
  confidence_score?: number;
}

export interface PricePoint {
  date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume: number;
}

export interface TickerAnalysis {
  ticker: string;
  company_name: string;
  sector: string;
  industry?: string;
  quant_summary: string;
  qualitative_summary: string;
  key_positive_factors: string[];
  key_negative_factors: string[];
  news_sentiment_score: number;
  risk_score: number;
  benefit_score: number;
  confidence_score: number;
  investment_view: string;
  time_horizon: string;
  monitoring_triggers: string[];
  short_advice: string;
  sources_used: string[];
  quant_metrics: Record<string, unknown>;
  fundamentals: Record<string, unknown>;
  price_history: PricePoint[];
  timestamp: string;
}

export interface RankingEntry {
  ticker: string;
  company_name: string;
  sector: string;
  benefit_score: number;
  risk_score: number;
  confidence_score: number;
  news_sentiment_score: number;
  composite_score: number;
  short_advice: string;
}

export interface BasketItem {
  ticker: string;
  weight: number;
  rationale: string;
}

export interface SectorCluster {
  sector: string;
  average_composite_score: number;
  average_risk_score: number;
  symbols: string[];
}

export interface WeeklySummary {
  run_date: string;
  ranking: RankingEntry[];
  top_tickers: string[];
  worst_tickers: string[];
  recommended_basket: BasketItem[];
  basket_rationale: string;
  sector_clusters: SectorCluster[];
  competitive_relationships: string[];
  supply_chain_links: string[];
  scenario_signals: string[];
  macro_themes: string[];
  watchlist: string[];
  systemic_risks: string[];
  llm_commentary?: string | null;
  generated_at: string;
}

export interface LatestRunResponse {
  run_date: string;
  weekly_summary?: WeeklySummary;
}

export interface TickersResponse {
  run_date?: string;
  tickers: TickerLight[];
}
