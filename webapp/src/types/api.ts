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

export interface FundamentalAnalysis {
  moat_assessment: string;
  management_quality: string;
  growth_prospects: string;
  financial_health_summary: string;
  fair_value_assessment: string;
  fundamental_score: number;
  fundamental_verdict: "undervalued" | "fairly_valued" | "overvalued" | string;
  key_strengths: string[];
  key_concerns: string[];
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
  fundamental_analysis?: FundamentalAnalysis | null;
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

export interface LiveQuote {
  symbol: string;
  period: string;
  current_price: number | null;
  change_1d: number | null;
  change_1m: number | null;
  change_3m: number | null;
  price_history: PricePoint[];
}

export interface NewsArticle {
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  summary: string;
}

export interface LiveNews {
  symbol: string;
  articles: NewsArticle[];
}

export interface MacroIndicator {
  symbol: string;
  name: string;
  category: string;
  current_value: number | null;
  change_1d: number | null;
  change_1m: number | null;
  change_3m: number | null;
}

export interface MacroAnalysis {
  run_date: string;
  macro_regime: string;
  market_breadth: string;
  key_macro_themes: string[];
  macro_risks: string[];
  sector_rotation_signal: string;
  yield_curve_interpretation: string;
  dollar_impact: string;
  macro_commentary: string;
  macro_score: number;
  indicators: MacroIndicator[];
  yield_curve_spread: number | null;
  vix_level: number | null;
  sector_performance: Record<string, number>;
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

export interface FailedTicker {
  symbol: string;
  error: string;
  stage: string;
}

export interface FailedTickersResponse {
  run_date: string;
  failed_tickers: FailedTicker[];
}
