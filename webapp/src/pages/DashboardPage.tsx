import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { BasketCard } from "../components/BasketCard";
import { LoadingState } from "../components/LoadingState";
import { RankingTable } from "../components/RankingTable";
import { ScoreCard } from "../components/ScoreCard";
import { TickerSearch } from "../components/TickerSearch";
import { getTickers, getWeeklySummaryLatest } from "../services/api";
import type { TickerLight, WeeklySummary } from "../types/api";

interface DashboardPageProps {
  onRunDateChange: (runDate: string | undefined) => void;
}

export function DashboardPage({ onRunDateChange }: DashboardPageProps) {
  const [summary, setSummary] = useState<WeeklySummary | null>(null);
  const [tickers, setTickers] = useState<TickerLight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sectorFilter, setSectorFilter] = useState("All");

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        setLoading(true);
        const [weekly, tickerRes] = await Promise.all([getWeeklySummaryLatest(), getTickers()]);
        if (!mounted) {
          return;
        }
        setSummary(weekly);
        setTickers(tickerRes.tickers);
        onRunDateChange(weekly.run_date);
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError((loadError as Error).message);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [onRunDateChange]);

  const sectors = useMemo(() => {
    if (!summary) {
      return ["All"];
    }
    const unique = Array.from(new Set(summary.ranking.map((item) => item.sector))).sort();
    return ["All", ...unique];
  }, [summary]);

  const filteredTickers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return tickers.filter((item) => {
      if (!normalized) {
        return true;
      }
      return (
        item.symbol.toLowerCase().includes(normalized) || item.company_name.toLowerCase().includes(normalized)
      );
    });
  }, [query, tickers]);

  if (loading) {
    return <LoadingState text="Loading weekly ranking..." />;
  }

  if (error) {
    return <div className="error-box">{error}</div>;
  }

  if (!summary) {
    return <div className="error-box">No weekly summary available.</div>;
  }

  const top1 = summary.ranking[0];
  const avgBenefit =
    summary.ranking.reduce((acc, item) => acc + item.benefit_score, 0) / Math.max(summary.ranking.length, 1);
  const avgRisk =
    summary.ranking.reduce((acc, item) => acc + item.risk_score, 0) / Math.max(summary.ranking.length, 1);

  const sectorClusters = summary.sector_clusters ?? [];
  const scenarioSignals = summary.scenario_signals ?? [];
  const relationships = summary.competitive_relationships ?? [];
  const supplyChainLinks = summary.supply_chain_links ?? [];

  return (
    <div className="page-grid">
      <section className="hero">
        <div>
          <p className="eyebrow">Weekly Snapshot</p>
          <h2>{top1 ? `${top1.ticker} leads the ranking` : "Ranking ready"}</h2>
          <p className="muted">Top themes and basket proposals are generated from quantitative and qualitative context.</p>
        </div>
        <div className="hero-metrics">
          <ScoreCard label="Top Ticker" value={top1?.ticker ?? "-"} tone="positive" />
          <ScoreCard label="Avg Benefit" value={avgBenefit.toFixed(1)} tone="positive" />
          <ScoreCard label="Avg Risk" value={avgRisk.toFixed(1)} tone="warning" />
          <ScoreCard label="Universe" value={String(summary.ranking.length)} tone="neutral" />
        </div>
      </section>

      <section className="controls-row">
        <TickerSearch query={query} onChange={setQuery} />
        <select value={sectorFilter} onChange={(event) => setSectorFilter(event.target.value)}>
          {sectors.map((sector) => (
            <option key={sector} value={sector}>
              {sector}
            </option>
          ))}
        </select>
      </section>

      <RankingTable items={summary.ranking} sectorFilter={sectorFilter} />

      <div className="side-grid">
        <BasketCard items={summary.recommended_basket} rationale={summary.basket_rationale} />

        <section className="panel">
          <div className="panel-header">
            <h3>Macro Themes</h3>
          </div>
          <ul className="bullet-list">
            {summary.macro_themes.map((theme) => (
              <li key={theme}>{theme}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h3>Watchlist</h3>
          </div>
          <div className="chip-row">
            {summary.watchlist.map((ticker) => (
              <Link key={ticker} className="chip" to={`/ticker/${ticker}`}>
                {ticker}
              </Link>
            ))}
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <h3>Sector Clusters</h3>
        </div>
        <div className="cluster-grid">
          {sectorClusters.map((cluster) => (
            <article className="cluster-card" key={cluster.sector}>
              <p className="ticker-symbol">{cluster.sector}</p>
              <p className="muted small">Avg score: {cluster.average_composite_score.toFixed(2)}</p>
              <p className="muted small">Avg risk: {cluster.average_risk_score.toFixed(2)}</p>
              <p className="small">{cluster.symbols.join(", ")}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel details-grid">
        <article>
          <h3>Scenario Signals</h3>
          <ul className="bullet-list">
            {scenarioSignals.map((signal) => (
              <li key={signal}>{signal}</li>
            ))}
          </ul>
        </article>
        <article>
          <h3>Competitive Relations</h3>
          <ul className="bullet-list">
            {relationships.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h4>Supply Chain Links</h4>
          <ul className="bullet-list">
            {supplyChainLinks.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Ticker Explorer</h3>
          <span>{filteredTickers.length} results</span>
        </div>
        <div className="ticker-grid">
          {filteredTickers.slice(0, 30).map((item) => (
            <Link className="ticker-card" key={item.symbol} to={`/ticker/${item.symbol}`}>
              <p className="ticker-symbol">{item.symbol}</p>
              <p>{item.company_name}</p>
              <p className="muted small">{item.sector}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
