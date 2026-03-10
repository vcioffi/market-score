from __future__ import annotations

from src.llm.schemas import TickerAnalysis
from src.portfolio.ranking import build_weekly_summary


def _analysis(symbol: str, sector: str, benefit: float, risk: float, sentiment: float) -> TickerAnalysis:
    return TickerAnalysis(
        ticker=symbol,
        company_name=symbol,
        sector=sector,
        quant_summary="summary",
        qualitative_summary="qual",
        key_positive_factors=["x"],
        key_negative_factors=["y"],
        news_sentiment_score=sentiment,
        risk_score=risk,
        benefit_score=benefit,
        confidence_score=70.0,
        investment_view="neutral",
        time_horizon="3-12 months",
        monitoring_triggers=["trigger"],
        short_advice="advice",
        sources_used=["test"],
        quant_metrics={"beta": 1.1, "rolling_volatility_20d": 0.25},
        fundamentals={},
        price_history=[],
    )


def test_weekly_summary_builds_ranking() -> None:
    analyses = [
        _analysis("AAA", "Tech", 75, 40, 60),
        _analysis("BBB", "Tech", 55, 50, 52),
        _analysis("CCC", "Healthcare", 68, 42, 58),
    ]

    summary = build_weekly_summary("2026-03-07", analyses)

    assert summary.run_date == "2026-03-07"
    assert len(summary.ranking) == 3
    assert summary.ranking[0].ticker == "AAA"
    assert len(summary.recommended_basket) > 0
