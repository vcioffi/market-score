"""Static analysis engine — no LLM required.

Produces rich, data-driven TickerAnalysis purely from quantitative metrics
and news headlines. Intended as a first-class analysis mode (not a fallback):
real market data and news are fetched, then every field is computed
deterministically from the numbers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.llm.fallback import _bound, _build_fallback_fundamental_analysis
from src.llm.pipeline import TickerLLMInput
from src.llm.schemas import TickerAnalysis
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _r(v: Any, d: int = 2) -> float | None:
    try:
        return round(float(v), d) if v is not None else None
    except (TypeError, ValueError):
        return None


def _pct(v: Any, d: int = 1, sign: bool = True) -> str | None:
    val = _r(v)
    if val is None:
        return None
    fmt = f"{val * 100:+.{d}f}%" if sign else f"{val * 100:.{d}f}%"
    return fmt


def _ma_distance(price: float | None, ma: float | None) -> float | None:
    try:
        return (float(price) / float(ma)) - 1.0 if price and ma else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# ── technical narrative ───────────────────────────────────────────────────────

def _rsi_label(rsi: float) -> str:
    if rsi >= 75:
        return "overbought"
    if rsi >= 60:
        return "bullish momentum"
    if rsi <= 25:
        return "oversold"
    if rsi <= 40:
        return "weak momentum"
    return "neutral"


def _vol_label(vol: float) -> str:
    if vol < 0.12:
        return "low"
    if vol < 0.25:
        return "moderate"
    if vol < 0.40:
        return "elevated"
    return "high"


def _sharpe_label(s: float) -> str:
    if s >= 1.5:
        return "strong"
    if s >= 0.8:
        return "good"
    if s >= 0.0:
        return "fair"
    return "negative"


def _beta_label(b: float) -> str:
    if b > 1.4:
        return "high-beta"
    if b < 0.6:
        return "low-beta / defensive"
    return "market-correlated"


def _build_quant_narrative(quant: dict) -> str:
    price = _r(quant.get("latest_close"))
    returns = quant.get("returns", {})
    ret_1m = _r(returns.get("1m"))
    ret_3m = _r(returns.get("3m"))
    ret_1y = _r(returns.get("1y"))
    vol = _r(quant.get("rolling_volatility_20d"))
    rsi = _r(quant.get("rsi_14"))
    sharpe = _r(quant.get("sharpe_ratio"))
    beta = _r(quant.get("beta"))
    drawdown = _r(quant.get("max_drawdown"))
    mas = quant.get("moving_averages", {})
    ma50 = _r(mas.get("ma_50"))
    ma200 = _r(mas.get("ma_200"))
    vs_ma50 = _ma_distance(price, ma50)
    vs_ma200 = _ma_distance(price, ma200)

    parts: list[str] = []

    # Price + returns
    price_str = f"${price:.2f}" if price else "n/a"
    ret_parts: list[str] = []
    if ret_1m is not None:
        ret_parts.append(f"1M {_pct(ret_1m)}")
    if ret_3m is not None:
        ret_parts.append(f"3M {_pct(ret_3m)}")
    if ret_1y is not None:
        ret_parts.append(f"1Y {_pct(ret_1y)}")
    parts.append(f"Price {price_str}" + (f" | Returns: {' / '.join(ret_parts)}" if ret_parts else ""))

    # RSI
    if rsi is not None:
        parts.append(f"RSI(14) {rsi:.1f} — {_rsi_label(rsi)}")

    # MA alignment
    ma_lines: list[str] = []
    if vs_ma50 is not None:
        d = "above" if vs_ma50 >= 0 else "below"
        ma_lines.append(f"{abs(vs_ma50 * 100):.1f}% {d} MA50 (${ma50:.2f})" if ma50 else f"{abs(vs_ma50 * 100):.1f}% {d} MA50")
    if vs_ma200 is not None:
        d = "above" if vs_ma200 >= 0 else "below"
        ma_lines.append(f"{abs(vs_ma200 * 100):.1f}% {d} MA200 (${ma200:.2f})" if ma200 else f"{abs(vs_ma200 * 100):.1f}% {d} MA200")
    if ma_lines:
        parts.append("Price " + ", ".join(ma_lines))

    # Volatility + risk metrics
    if vol is not None:
        parts.append(f"20d volatility {vol * 100:.1f}% ({_vol_label(vol)})")
    if drawdown is not None:
        parts.append(f"Max drawdown {drawdown * 100:.1f}%")
    if sharpe is not None:
        parts.append(f"Sharpe {sharpe:.2f} ({_sharpe_label(sharpe)})")
    if beta is not None:
        parts.append(f"Beta {beta:.2f} ({_beta_label(beta)})")

    return ". ".join(parts) + "." if parts else "Quantitative data unavailable for this ticker."


# ── news narrative ────────────────────────────────────────────────────────────

def _build_news_narrative(
    company_news: list[dict],
    sector_news: list[dict],
    company_sentiment: dict | None,
    sector_sentiment: dict | None,
) -> str:
    parts: list[str] = []

    co_titles = [a.get("title", "").strip() for a in company_news[:3] if a.get("title")]
    if co_titles:
        parts.append("News: " + " | ".join(co_titles))

    sec_titles = [a.get("title", "").strip() for a in sector_news[:2] if a.get("title")]
    if sec_titles:
        parts.append("Sector: " + " | ".join(sec_titles))

    if isinstance(company_sentiment, dict):
        score = company_sentiment.get("score_0_100")
        label = company_sentiment.get("label", "")
        rationale = (company_sentiment.get("rationale") or "").strip()
        if score is not None:
            sent_str = f"Company sentiment {score}/100 ({label})"
            if rationale:
                sent_str += f" — {rationale[:120]}"
            parts.append(sent_str)

    if isinstance(sector_sentiment, dict):
        score = sector_sentiment.get("score_0_100")
        label = sector_sentiment.get("label", "")
        if score is not None:
            parts.append(f"Sector sentiment {score}/100 ({label})")

    return ". ".join(parts) + "." if parts else "No recent news available in the current window."


# ── positive/negative factors ─────────────────────────────────────────────────

def _build_factors(
    quant: dict,
    fundamentals: dict,
    news_payload: dict,
) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    negatives: list[str] = []

    price = _r(quant.get("latest_close"))
    returns = quant.get("returns", {})
    ret_1m = _r(returns.get("1m"))
    ret_3m = _r(returns.get("3m"))
    ret_1y = _r(returns.get("1y"))
    vol = _r(quant.get("rolling_volatility_20d"))
    rsi = _r(quant.get("rsi_14"))
    sharpe = _r(quant.get("sharpe_ratio"))
    drawdown = _r(quant.get("max_drawdown"))
    signals = quant.get("signals", {})
    mas = quant.get("moving_averages", {})
    ma50 = _r(mas.get("ma_50"))
    ma200 = _r(mas.get("ma_200"))
    vs_ma50 = _ma_distance(price, ma50)
    vs_ma200 = _ma_distance(price, ma200)

    # ── Technical factors ──
    if ret_1y is not None:
        if ret_1y > 0.20:
            positives.append(f"Strong 1Y return {_pct(ret_1y)} reflects sustained outperformance")
        elif ret_1y > 0.05:
            positives.append(f"Positive 1Y return {_pct(ret_1y)} shows moderate trend strength")
        elif ret_1y < -0.20:
            negatives.append(f"1Y loss of {_pct(ret_1y, sign=False)} raises sustained downtrend concern")
        elif ret_1y < -0.05:
            negatives.append(f"Negative 1Y return {_pct(ret_1y)} signals medium-term weakness")

    if ret_3m is not None:
        if ret_3m > 0.08:
            positives.append(f"3M momentum {_pct(ret_3m)} supports near-term continuation")
        elif ret_3m < -0.08:
            negatives.append(f"3M pullback {_pct(ret_3m)} signals short-term distribution pressure")

    if rsi is not None:
        if 45 <= rsi <= 68:
            positives.append(f"RSI {rsi:.1f} in healthy zone — momentum without overbought exhaustion")
        elif rsi > 75:
            negatives.append(f"RSI {rsi:.1f} overbought — elevated mean-reversion risk near term")
        elif rsi < 30:
            positives.append(f"RSI {rsi:.1f} oversold — potential contrarian entry / bounce setup")

    if vs_ma200 is not None:
        if vs_ma200 > 0.05:
            positives.append(f"Price {abs(vs_ma200 * 100):.1f}% above MA200 confirms long-term uptrend intact")
        elif vs_ma200 < -0.05:
            negatives.append(f"Price {abs(vs_ma200 * 100):.1f}% below MA200 — long-term trend structure broken")

    if vs_ma50 is not None:
        if vs_ma50 > 0:
            positives.append(f"Trading above MA50 (${ma50:.2f}) — medium-term bullish alignment" if ma50 else "Trading above MA50 — medium-term bullish alignment")
        else:
            negatives.append(f"Below MA50 (${ma50:.2f}) — medium-term trend under pressure" if ma50 else "Below MA50 — medium-term trend under pressure")

    if sharpe is not None:
        if sharpe >= 1.2:
            positives.append(f"Sharpe ratio {sharpe:.2f} — superior risk-adjusted return profile")
        elif sharpe < 0:
            negatives.append(f"Negative Sharpe ({sharpe:.2f}) — returns insufficient to compensate for volatility")

    if vol is not None and vol > 0.35:
        negatives.append(f"High 20d volatility {vol * 100:.1f}% amplifies drawdown risk in adverse scenarios")

    if drawdown is not None and abs(drawdown) > 0.30:
        negatives.append(f"Max drawdown {abs(drawdown) * 100:.1f}% — deep historical peak-to-trough loss on record")

    if signals.get("breakout"):
        positives.append("Breakout signal active — price approaching multi-week high with volume expansion")
    if signals.get("volatility_compression"):
        positives.append("Volatility squeeze (Bollinger compression) — potential for directional expansion ahead")

    # ── Fundamental factors ──
    pe = fundamentals.get("pe")
    fwd_pe = fundamentals.get("forward_pe")
    roe = _r(fundamentals.get("roe"))
    rev_gr = _r(fundamentals.get("revenue_growth"))
    op_margin = _r(fundamentals.get("operating_margin"))
    eps_gr = _r(fundamentals.get("eps_growth"))
    d_e = _r(fundamentals.get("debt_to_equity"))
    mos = _r(fundamentals.get("margin_of_safety"))
    current_ratio = _r(fundamentals.get("current_ratio"))
    div_yield = _r(fundamentals.get("dividend_yield"))

    if roe is not None:
        if roe > 0.20:
            positives.append(f"ROE {roe * 100:.1f}% — high return on equity signals durable competitive advantage")
        elif roe < 0:
            negatives.append(f"Negative ROE {roe * 100:.1f}% — equity value erosion at current profitability")

    if rev_gr is not None:
        if rev_gr > 0.12:
            positives.append(f"Revenue growth {_pct(rev_gr)} YoY — strong top-line expansion supports valuation")
        elif rev_gr < -0.05:
            negatives.append(f"Revenue declining {_pct(rev_gr)} — top-line contraction pressures margin runway")

    if op_margin is not None:
        if op_margin > 0.20:
            positives.append(f"Operating margin {op_margin * 100:.1f}% — exceptional cost discipline and pricing power")
        elif op_margin > 0.10:
            positives.append(f"Healthy operating margin {op_margin * 100:.1f}%")
        elif op_margin < 0:
            negatives.append(f"Negative operating margin {op_margin * 100:.1f}% — burning cash at operating level")

    if eps_gr is not None and eps_gr > 0.15:
        positives.append(f"EPS growth {_pct(eps_gr)} demonstrates earnings leverage on revenue")

    if d_e is not None:
        if d_e > 200:
            negatives.append(f"High leverage D/E {d_e:.0f}% — interest coverage risk in rising-rate environment")
        elif d_e < 30:
            positives.append(f"Low leverage D/E {d_e:.0f}% — financial flexibility and stress resilience")

    if mos is not None:
        if mos >= 25:
            positives.append(f"Graham margin of safety {mos:.1f}% — trading materially below intrinsic value estimate")
        elif mos <= -30:
            negatives.append(f"Price {abs(mos):.1f}% above Graham Number — limited downside protection at current valuation")

    if pe is not None and pe > 0:
        if pe > 40:
            negatives.append(f"P/E {pe:.1f}x requires near-perfect execution; any earnings miss could be costly")
        elif pe < 12:
            positives.append(f"Low P/E {pe:.1f}x — potential value opportunity if earnings hold")

    if current_ratio is not None and current_ratio < 1.0:
        negatives.append(f"Current ratio {current_ratio:.1f} — near-term liquidity pressure")

    if div_yield is not None and div_yield > 0.025:
        positives.append(f"Dividend yield {div_yield * 100:.1f}% provides income and limits downside")

    # ── Sentiment factor ──
    co_sent = news_payload.get("company_sentiment") or {}
    if isinstance(co_sent, dict):
        score = co_sent.get("score_0_100")
        if isinstance(score, (int, float)):
            if score >= 65:
                positives.append(f"News sentiment constructive ({score:.0f}/100) — recent headlines support near-term view")
            elif score <= 35:
                negatives.append(f"News sentiment cautious ({score:.0f}/100) — recent headlines flag headwinds")

    return positives, negatives


# ── monitoring triggers ───────────────────────────────────────────────────────

def _build_monitoring_triggers(
    quant: dict,
    fundamentals: dict,
    profile_symbol: str,
    peers: list[str],
) -> list[str]:
    triggers: list[str] = []

    price = _r(quant.get("latest_close"))
    mas = quant.get("moving_averages", {})
    ma50 = _r(mas.get("ma_50"))
    ma200 = _r(mas.get("ma_200"))

    if ma50:
        ma50_str = f"${ma50:.2f}" if price else str(ma50)
        triggers.append(f"Break below MA50 ({ma50_str}) on above-average volume — signals trend deterioration")
    if ma200:
        ma200_str = f"${ma200:.2f}" if price else str(ma200)
        triggers.append(f"MA200 ({ma200_str}) is key long-term support — sustained close below warrants position review")

    triggers.append("Earnings report: watch for guidance revision, margin trajectory, and beat/miss vs consensus")

    if peers:
        peers_str = ", ".join(peers[:3])
        triggers.append(f"Relative performance vs peers ({peers_str}) — divergence may signal stock-specific risk")
    else:
        triggers.append("Sector ETF performance — broad sector weakness increases individual name risk")

    pe = fundamentals.get("pe")
    if pe and pe > 30:
        triggers.append(f"Valuation re-rating: at P/E {pe:.1f}x, any deceleration in growth outlook is high-impact")

    return triggers[:4]


# ── scores ────────────────────────────────────────────────────────────────────

def _compute_scores(
    quant: dict,
    fundamentals: dict,
    news_payload: dict,
) -> tuple[float, float, float, float]:
    """Returns (benefit_score, risk_score, confidence_score, news_sentiment_score)."""
    returns = quant.get("returns", {})
    ret_1m = _r(returns.get("1m")) or 0.0
    ret_3m = _r(returns.get("3m")) or 0.0
    ret_1y = _r(returns.get("1y")) or 0.0
    momentum = _r(quant.get("simple_momentum_3m")) or 0.0
    vol = abs(_r(quant.get("rolling_volatility_20d")) or 0.25)
    drawdown = abs(_r(quant.get("max_drawdown")) or 0.15)
    beta = abs(_r(quant.get("beta")) or 1.0)
    rsi = _r(quant.get("rsi_14")) or 50.0
    sharpe = _r(quant.get("sharpe_ratio")) or 0.0

    # Sentiment
    co_sent = news_payload.get("company_sentiment") or {}
    sec_sent = news_payload.get("sector_sentiment") or {}
    scores_raw = [
        float(v) for v in [
            co_sent.get("score_0_100") if isinstance(co_sent, dict) else None,
            sec_sent.get("score_0_100") if isinstance(sec_sent, dict) else None,
        ]
        if v is not None
    ]
    if scores_raw:
        news_sentiment = _bound(sum(scores_raw) / len(scores_raw))
    else:
        # keyword fallback
        company_news = news_payload.get("company_news", [])
        POSITIVE = {"growth", "upgrade", "beat", "expansion", "record", "strong", "partnership", "improved", "outperform"}
        NEGATIVE = {"downgrade", "lawsuit", "delay", "weak", "recall", "decline", "cut", "warning", "investigation"}
        base = 50.0
        for item in company_news:
            text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            base += 4.0 * sum(w in text for w in POSITIVE)
            base -= 4.0 * sum(w in text for w in NEGATIVE)
        news_sentiment = _bound(base)

    # Fundamental boost/drag
    fund_delta = 0.0
    roe = _r(fundamentals.get("roe"))
    rev_gr = _r(fundamentals.get("revenue_growth"))
    op_margin = _r(fundamentals.get("operating_margin"))
    d_e = _r(fundamentals.get("debt_to_equity"))
    mos = _r(fundamentals.get("margin_of_safety"))

    if roe is not None:
        fund_delta += min(roe * 50, 8) if roe > 0 else -5
    if rev_gr is not None:
        fund_delta += min(rev_gr * 40, 8) if rev_gr > 0 else -4
    if op_margin is not None:
        fund_delta += min(op_margin * 30, 6) if op_margin > 0.10 else (0 if op_margin > 0 else -4)
    if d_e is not None:
        fund_delta -= min(d_e / 200, 6) if d_e > 100 else 0
    if mos is not None:
        fund_delta += min(mos / 10, 8) if mos > 0 else max(mos / 10, -6)

    benefit_score = _bound(
        55
        + (ret_1m + ret_3m + ret_1y + momentum) * 30
        + (news_sentiment - 50) * 0.25
        + sharpe * 3
        + fund_delta
    )
    risk_score = _bound(
        35
        + vol * 90
        + drawdown * 70
        + (beta - 1.0) * 8
        + (12 if rsi > 75 else 0)
        + (-6 if rsi < 35 else 0)
    )

    # Confidence: based on data completeness
    data_points = sum(
        1 for v in [
            quant.get("sharpe_ratio"), quant.get("rsi_14"), quant.get("beta"),
            fundamentals.get("pe"), fundamentals.get("revenue_growth"),
            fundamentals.get("operating_margin"), fundamentals.get("roe"),
        ]
        if v is not None
    )
    co_articles = len(news_payload.get("company_news") or [])
    confidence_score = _bound(40 + data_points * 7 + co_articles * 2)

    return benefit_score, risk_score, confidence_score, news_sentiment


def _investment_view_and_horizon(benefit: float, risk: float) -> tuple[str, str, str]:
    gap = benefit - risk
    if gap > 22:
        return "constructive", "6–18 months", (
            "Setup clearly favors the bull case. Consider phased accumulation; "
            "manage position size relative to portfolio volatility."
        )
    if gap > 10:
        return "selective bullish", "3–12 months", (
            "Attractive risk/reward with caveats. Wait for a clean technical entry "
            "or minor pullback to improve the margin of safety."
        )
    if gap > -5:
        return "neutral", "1–6 months", (
            "Risk and reward roughly balanced at current levels. "
            "Monitor for a catalyst or cleaner setup before committing capital."
        )
    return "defensive", "short-term caution", (
        "Risk profile dominates. Prefer patience until volatility normalises, "
        "trend improves, or fundamentals provide a clearer floor."
    )


# ── main builder ──────────────────────────────────────────────────────────────

def _build_static_ticker_analysis(entry: TickerLLMInput) -> TickerAnalysis:
    profile = entry.profile
    quant = entry.metrics_payload.get("quant", {})
    fundamentals = entry.metrics_payload.get("fundamentals", {})
    company_news = entry.news_payload.get("company_news", [])
    sector_news = entry.news_payload.get("sector_news", [])
    co_sent = entry.news_payload.get("company_sentiment") or {}
    sec_sent = entry.news_payload.get("sector_sentiment") or {}
    sources_used: list[str] = entry.news_payload.get("sources_used", []) + ["static_engine"]

    benefit, risk, confidence, news_sentiment = _compute_scores(quant, fundamentals, entry.news_payload)
    investment_view, horizon, short_advice = _investment_view_and_horizon(benefit, risk)
    positives, negatives = _build_factors(quant, fundamentals, entry.news_payload)
    triggers = _build_monitoring_triggers(quant, fundamentals, profile.symbol, profile.peers or [])
    fundamental_analysis = _build_fallback_fundamental_analysis(fundamentals)

    return TickerAnalysis(
        ticker=profile.symbol,
        company_name=profile.company_name,
        sector=profile.sector,
        industry=profile.industry,
        quant_summary=_build_quant_narrative(quant),
        qualitative_summary=_build_news_narrative(company_news, sector_news, co_sent or None, sec_sent or None),
        key_positive_factors=positives[:5] or ["No dominant positive signal from current dataset"],
        key_negative_factors=negatives[:5] or ["No dominant downside signal from current dataset"],
        news_sentiment_score=round(news_sentiment, 2),
        risk_score=round(risk, 2),
        benefit_score=round(benefit, 2),
        confidence_score=round(confidence, 2),
        investment_view=investment_view,
        time_horizon=horizon,
        monitoring_triggers=triggers,
        short_advice=short_advice,
        sources_used=list(dict.fromkeys(sources_used)),
        quant_metrics=quant,
        fundamentals=fundamentals,
        fundamental_analysis=fundamental_analysis,
        price_history=entry.metrics_payload.get("price_history", []),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ── engine ────────────────────────────────────────────────────────────────────

class StaticAnalysisEngine:
    """Deterministic analysis engine — fetches real data, zero LLM calls."""

    def run(
        self,
        inputs: list[TickerLLMInput],
        **_kwargs: Any,
    ) -> tuple[dict[str, TickerAnalysis], dict]:
        results: dict[str, TickerAnalysis] = {}
        for entry in inputs:
            try:
                results[entry.profile.symbol] = _build_static_ticker_analysis(entry)
                LOGGER.debug("Static analysis: %s", entry.profile.symbol)
            except Exception as exc:
                LOGGER.warning("Static analysis failed for %s: %s", entry.profile.symbol, exc)
        return results, {"mode": "static", "processed": len(results)}
