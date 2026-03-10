from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.llm.schemas import TickerAnalysis
from src.tickers.models import TickerProfile

POSITIVE_WORDS = {
    "growth",
    "upgrade",
    "beat",
    "expansion",
    "partnership",
    "improved",
    "strong",
    "record",
    "outperform",
}
NEGATIVE_WORDS = {
    "downgrade",
    "lawsuit",
    "delay",
    "weak",
    "recall",
    "decline",
    "cut",
    "warning",
    "investigation",
}


def _bound(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _sentiment_from_news(news_items: list[dict]) -> float:
    if not news_items:
        return 50.0
    score = 50.0
    for item in news_items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        score += 4.0 * sum(word in text for word in POSITIVE_WORDS)
        score -= 4.0 * sum(word in text for word in NEGATIVE_WORDS)
    return _bound(score)


def _build_quant_summary(quant: dict) -> str:
    returns = quant.get("returns", {})
    one_year = returns.get("1y")
    drawdown = quant.get("max_drawdown")
    volatility = quant.get("rolling_volatility_20d")
    rsi = quant.get("rsi_14")

    return (
        f"1Y return={one_year:.2%} | max drawdown={drawdown:.2%} | "
        f"20d vol={volatility:.2%} | RSI14={rsi:.1f}"
        if all(value is not None for value in [one_year, drawdown, volatility, rsi])
        else "Quant picture mixed due to partial coverage; monitor trend strength and volatility regime."
    )


def _build_qualitative_summary(company_news: list[dict], sector_news: list[dict]) -> str:
    headlines = [item.get("title", "") for item in company_news[:2] + sector_news[:2]]
    if not headlines:
        return "No major validated catalysts in window; rely more heavily on quantitative setup."
    return " | ".join(headlines)


def build_fallback_ticker_analysis(
    profile: TickerProfile,
    metrics_payload: dict,
    news_payload: dict,
    sources_used: list[str],
) -> TickerAnalysis:
    quant = metrics_payload.get("quant", {})
    fundamentals = metrics_payload.get("fundamentals", {})
    company_news = news_payload.get("company_news", [])
    sector_news = news_payload.get("sector_news", [])

    one_month = quant.get("returns", {}).get("1m") or 0.0
    three_month = quant.get("returns", {}).get("3m") or 0.0
    one_year = quant.get("returns", {}).get("1y") or 0.0
    momentum = quant.get("simple_momentum_3m") or 0.0
    volatility = quant.get("rolling_volatility_20d") or 0.25
    drawdown = abs(quant.get("max_drawdown") or 0.15)
    beta = abs(quant.get("beta") or 1.0)
    rsi = quant.get("rsi_14") or 50.0

    company_sentiment = news_payload.get("company_sentiment") or {}
    sector_sentiment = news_payload.get("sector_sentiment") or {}
    company_sentiment_score = company_sentiment.get("score_0_100") if isinstance(company_sentiment, dict) else None
    sector_sentiment_score = sector_sentiment.get("score_0_100") if isinstance(sector_sentiment, dict) else None

    sentiment_candidates = [
        value
        for value in (company_sentiment_score, sector_sentiment_score)
        if isinstance(value, (float, int))
    ]
    sentiment_score = (
        _bound(float(sum(sentiment_candidates)) / len(sentiment_candidates))
        if sentiment_candidates
        else _sentiment_from_news(company_news + sector_news)
    )

    benefit_score = _bound(55 + (one_month + three_month + one_year + momentum) * 35 + (sentiment_score - 50) * 0.3)
    risk_score = _bound(40 + volatility * 90 + drawdown * 80 + (beta - 1) * 10 + (10 if rsi > 75 else 0))

    data_points = 0
    for value in [
        quant.get("sharpe_ratio"),
        quant.get("sortino_ratio"),
        quant.get("correlation_benchmark"),
        fundamentals.get("revenue_growth"),
        fundamentals.get("operating_margin"),
    ]:
        if value is not None:
            data_points += 1

    confidence_score = _bound(45 + data_points * 8 + len(company_news) * 2)

    score_gap = benefit_score - risk_score
    if score_gap > 18:
        investment_view = "constructive"
        horizon = "6-18 months"
        advice = "Setup favors gradual accumulation if volatility remains controlled."
    elif score_gap > 5:
        investment_view = "selective bullish"
        horizon = "3-12 months"
        advice = "Potentially attractive, but wait for confirmation on trend and news flow."
    elif score_gap > -8:
        investment_view = "neutral"
        horizon = "1-6 months"
        advice = "Monitor closely; current risk/reward is balanced, not a clear edge yet."
    else:
        investment_view = "defensive"
        horizon = "short-term caution"
        advice = "Risk profile dominates; prefer patience until volatility and drawdown improve."

    positives = []
    negatives = []

    if one_year > 0:
        positives.append("Positive medium-term return profile")
    if sentiment_score >= 55:
        positives.append("News flow shows constructive bias")
    if quant.get("signals", {}).get("breakout"):
        positives.append("Price action is near breakout zone")
    if fundamentals.get("revenue_growth") and fundamentals.get("revenue_growth") > 0.05:
        positives.append("Revenue growth supports the thesis")

    if volatility > 0.35:
        negatives.append("Elevated realized volatility")
    if drawdown > 0.25:
        negatives.append("Deep drawdown history")
    if rsi > 75:
        negatives.append("RSI indicates near-term overbought conditions")
    if sentiment_score <= 45:
        negatives.append("Recent headlines are cautious or mixed")

    monitoring_triggers = [
        "Break below 50-day moving average with rising volume",
        "Material change in earnings guidance or margin trajectory",
        "Sector-level risk events affecting peer group sentiment",
    ]

    return TickerAnalysis(
        ticker=profile.symbol,
        company_name=profile.company_name,
        sector=profile.sector,
        industry=profile.industry,
        quant_summary=_build_quant_summary(quant),
        qualitative_summary=_build_qualitative_summary(company_news, sector_news),
        key_positive_factors=positives[:5] or ["No clear positive edge from current dataset"],
        key_negative_factors=negatives[:5] or ["No dominant downside signal detected"],
        news_sentiment_score=round(sentiment_score, 2),
        risk_score=round(risk_score, 2),
        benefit_score=round(benefit_score, 2),
        confidence_score=round(confidence_score, 2),
        investment_view=investment_view,
        time_horizon=horizon,
        monitoring_triggers=monitoring_triggers,
        short_advice=advice,
        sources_used=list(dict.fromkeys(sources_used)),
        quant_metrics=quant,
        fundamentals=fundamentals,
        price_history=metrics_payload.get("price_history", []),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def parse_json_from_model_output(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    # Prefer strict parse first for valid JSON mode outputs.
    try:
        direct = json.loads(text)
        if isinstance(direct, dict):
            return direct
        raise ValueError("Model output JSON is not an object")
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output")

    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model output JSON is not an object")
    return parsed
