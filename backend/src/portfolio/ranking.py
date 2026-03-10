from __future__ import annotations

from collections import defaultdict

from src.llm.schemas import BasketItem, RankingEntry, SectorCluster, TickerAnalysis, WeeklySummary


def _composite_score(item: TickerAnalysis) -> float:
    return round(
        (item.benefit_score * 0.45)
        + (item.news_sentiment_score * 0.15)
        + (item.confidence_score * 0.20)
        - (item.risk_score * 0.30),
        3,
    )


def _ranking(analyses: list[TickerAnalysis]) -> list[RankingEntry]:
    ranking = [
        RankingEntry(
            ticker=item.ticker,
            company_name=item.company_name,
            sector=item.sector,
            benefit_score=item.benefit_score,
            risk_score=item.risk_score,
            confidence_score=item.confidence_score,
            news_sentiment_score=item.news_sentiment_score,
            composite_score=_composite_score(item),
            short_advice=item.short_advice,
        )
        for item in analyses
    ]
    ranking.sort(key=lambda row: row.composite_score, reverse=True)
    return ranking


def _basket_from_ranking(ranking: list[RankingEntry], size: int = 8) -> list[BasketItem]:
    picks: list[RankingEntry] = []
    sector_limits: dict[str, int] = defaultdict(int)

    for row in ranking:
        if len(picks) >= size:
            break
        if sector_limits[row.sector] >= 2:
            continue
        picks.append(row)
        sector_limits[row.sector] += 1

    if not picks:
        return []

    weight = round(1.0 / len(picks), 4)
    return [
        BasketItem(
            ticker=row.ticker,
            weight=weight,
            rationale=f"Top composite score in {row.sector} with balanced risk profile",
        )
        for row in picks
    ]


def _sector_clusters(ranking: list[RankingEntry]) -> list[SectorCluster]:
    grouped: dict[str, list[RankingEntry]] = defaultdict(list)
    for row in ranking:
        grouped[row.sector].append(row)

    clusters: list[SectorCluster] = []
    for sector, rows in grouped.items():
        clusters.append(
            SectorCluster(
                sector=sector,
                average_composite_score=round(sum(item.composite_score for item in rows) / len(rows), 3),
                average_risk_score=round(sum(item.risk_score for item in rows) / len(rows), 3),
                symbols=[item.ticker for item in rows[:6]],
            )
        )
    clusters.sort(key=lambda row: row.average_composite_score, reverse=True)
    return clusters


def _competitive_relationships(ranking: list[RankingEntry]) -> list[str]:
    grouped: dict[str, list[RankingEntry]] = defaultdict(list)
    for row in ranking:
        grouped[row.sector].append(row)

    lines: list[str] = []
    for sector, rows in grouped.items():
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda item: item.composite_score, reverse=True)
        leader, challenger = rows[0], rows[1]
        lines.append(
            f"{leader.ticker} vs {challenger.ticker} in {sector}: leadership remains with {leader.ticker} on current composite scores."
        )
    return lines[:8]


def _supply_chain_links(ranking: list[RankingEntry]) -> list[str]:
    sectors = {row.sector for row in ranking[:20]}
    links: list[str] = []

    if "Technology" in sectors and "Communication Services" in sectors:
        links.append("AI infrastructure and cloud platforms remain mutually reinforcing across software and communication demand.")
    if "Energy" in sectors and "Industrials" in sectors:
        links.append("Energy price regime can propagate into industrial margins and capex timing.")
    if "Healthcare" in sectors and "Technology" in sectors:
        links.append("Automation and data tooling continue to influence healthcare operating efficiency.")

    if not links:
        links.append("No dominant cross-sector supply-chain linkage detected from current ranking sample.")

    return links[:5]


def _scenario_signals(ranking: list[RankingEntry], clusters: list[SectorCluster]) -> list[str]:
    signals: list[str] = []

    if clusters:
        top_cluster = clusters[0]
        signals.append(
            f"Scenario leadership: {top_cluster.sector} with average composite {top_cluster.average_composite_score:.2f}."
        )

    high_risk_share = [row for row in ranking if row.risk_score >= 60]
    if ranking:
        ratio = len(high_risk_share) / len(ranking)
        signals.append(f"High-risk share in universe: {ratio:.1%} of names above risk score 60.")

    momentum_leaders = [row.ticker for row in ranking[:5]]
    if momentum_leaders:
        signals.append(f"Momentum leadership basket: {', '.join(momentum_leaders)}.")

    return signals[:6]


def _macro_themes(ranking: list[RankingEntry]) -> list[str]:
    top = ranking[:15]
    if not top:
        return []

    sector_frequency: dict[str, int] = defaultdict(int)
    for row in top:
        sector_frequency[row.sector] += 1

    ordered = sorted(sector_frequency.items(), key=lambda item: item[1], reverse=True)
    themes = [f"Leadership from {sector} ({count} names in top 15)" for sector, count in ordered[:4]]
    themes.append("Risk discipline remains critical due to cross-sector volatility pockets")
    return themes


def _watchlist(ranking: list[RankingEntry]) -> list[str]:
    candidates = [
        row for row in ranking if row.benefit_score > 58 and row.risk_score > 52 and row.composite_score > 20
    ]
    return [row.ticker for row in candidates[:10]]


def _systemic_risks(analyses: list[TickerAnalysis]) -> list[str]:
    risks: list[str] = []

    elevated_beta = [
        row
        for row in analyses
        if isinstance(row.quant_metrics.get("beta"), (float, int)) and row.quant_metrics["beta"] > 1.35
    ]
    elevated_vol = [
        row
        for row in analyses
        if isinstance(row.quant_metrics.get("rolling_volatility_20d"), (float, int))
        and row.quant_metrics["rolling_volatility_20d"] > 0.45
    ]

    if len(elevated_beta) >= 8:
        risks.append("Many constituents have beta above 1.35 versus benchmark; market shocks can amplify drawdowns.")
    if len(elevated_vol) >= 8:
        risks.append("Realized volatility remains elevated in a meaningful part of the universe.")

    if not risks:
        risks.append("No dominant systemic alert detected, but monitor macro rate and liquidity regime changes.")

    return risks


def build_weekly_summary(run_date: str, analyses: list[TickerAnalysis]) -> WeeklySummary:
    ranking = _ranking(analyses)
    basket = _basket_from_ranking(ranking)
    clusters = _sector_clusters(ranking)

    basket_text = (
        "Diversified basket selected from highest composite names with sector caps to reduce concentration risk."
        if basket
        else "No basket generated due to missing ticker analyses."
    )

    return WeeklySummary(
        run_date=run_date,
        ranking=ranking,
        top_tickers=[row.ticker for row in ranking[:10]],
        worst_tickers=[row.ticker for row in ranking[-10:]] if len(ranking) > 10 else [row.ticker for row in ranking],
        recommended_basket=basket,
        basket_rationale=basket_text,
        sector_clusters=clusters,
        competitive_relationships=_competitive_relationships(ranking),
        supply_chain_links=_supply_chain_links(ranking),
        scenario_signals=_scenario_signals(ranking, clusters),
        macro_themes=_macro_themes(ranking),
        watchlist=_watchlist(ranking),
        systemic_risks=_systemic_risks(analyses),
        llm_commentary=None,
    )
