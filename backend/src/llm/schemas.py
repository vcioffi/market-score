from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int = 0


class TickerAnalysisLLM(BaseModel):
    """Schema used for the LLM structured output request.

    Excludes price_history, quant_metrics, fundamentals, and timestamp which are
    injected by the pipeline — keeping the LLM response compact and within token budgets.
    """

    ticker: str
    company_name: str
    sector: str
    industry: str
    quant_summary: str
    qualitative_summary: str
    key_positive_factors: list[str] = Field(default_factory=list)
    key_negative_factors: list[str] = Field(default_factory=list)
    news_sentiment_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    benefit_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    investment_view: str
    time_horizon: str
    monitoring_triggers: list[str] = Field(default_factory=list)
    short_advice: str
    sources_used: list[str] = Field(default_factory=list)


class TickerAnalysis(BaseModel):
    ticker: str
    company_name: str
    sector: str
    industry: str | None = None
    quant_summary: str
    qualitative_summary: str
    key_positive_factors: list[str] = Field(default_factory=list)
    key_negative_factors: list[str] = Field(default_factory=list)
    news_sentiment_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    benefit_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    investment_view: str
    time_horizon: str
    monitoring_triggers: list[str] = Field(default_factory=list)
    short_advice: str
    sources_used: list[str] = Field(default_factory=list)
    quant_metrics: dict = Field(default_factory=dict)
    fundamentals: dict = Field(default_factory=dict)
    price_history: list[PricePoint] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RankingEntry(BaseModel):
    ticker: str
    company_name: str
    sector: str
    benefit_score: float
    risk_score: float
    confidence_score: float
    news_sentiment_score: float
    composite_score: float
    short_advice: str


class BasketItem(BaseModel):
    ticker: str
    weight: float
    rationale: str


class SectorCluster(BaseModel):
    sector: str
    average_composite_score: float
    average_risk_score: float
    symbols: list[str]


class WeeklyLLMCommentary(BaseModel):
    """Slim LLM output schema: only the narrative commentary.

    The full WeeklySummary is already computed deterministically by the ranking pipeline.
    The LLM only needs to generate the free-text commentary — everything else is merged
    from the pre-computed summary after the call completes.
    """

    llm_commentary: str


class WeeklySummary(BaseModel):
    run_date: str
    ranking: list[RankingEntry]
    top_tickers: list[str]
    worst_tickers: list[str]
    recommended_basket: list[BasketItem]
    basket_rationale: str
    sector_clusters: list[SectorCluster]
    competitive_relationships: list[str] = Field(default_factory=list)
    supply_chain_links: list[str] = Field(default_factory=list)
    scenario_signals: list[str] = Field(default_factory=list)
    macro_themes: list[str]
    watchlist: list[str]
    systemic_risks: list[str]
    llm_commentary: str | None = None
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def export_json_schemas(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)

    (target_dir / "ticker_analysis.schema.json").write_text(
        json.dumps(TickerAnalysis.model_json_schema(), indent=2),
        encoding="utf-8",
    )
    (target_dir / "weekly_summary.schema.json").write_text(
        json.dumps(WeeklySummary.model_json_schema(), indent=2),
        encoding="utf-8",
    )
