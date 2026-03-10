import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { LoadingState } from "../components/LoadingState";
import { PriceChart } from "../components/PriceChart";
import { ScoreCard } from "../components/ScoreCard";
import { getTicker } from "../services/api";
import type { TickerAnalysis } from "../types/api";

function formatPercent(value: unknown): string {
  if (typeof value !== "number") {
    return "n/a";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: unknown): string {
  if (typeof value !== "number") {
    return "n/a";
  }
  return value.toFixed(2);
}

export function TickerDetailPage() {
  const { symbol } = useParams();
  const [ticker, setTicker] = useState<TickerAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!symbol) {
        return;
      }
      try {
        setLoading(true);
        const payload = await getTicker(symbol);
        if (!mounted) {
          return;
        }
        setTicker(payload);
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
  }, [symbol]);

  const returns = useMemo(() => {
    if (!ticker) {
      return {};
    }
    return (ticker.quant_metrics.returns as Record<string, unknown>) || {};
  }, [ticker]);

  if (loading) {
    return <LoadingState text="Loading ticker detail..." />;
  }

  if (error) {
    return <div className="error-box">{error}</div>;
  }

  if (!ticker) {
    return <div className="error-box">Ticker not found.</div>;
  }

  return (
    <div className="page-grid">
      <section className="hero compact">
        <div>
          <p className="eyebrow">Ticker Detail</p>
          <h2>
            {ticker.company_name} <span className="muted">({ticker.ticker})</span>
          </h2>
          <p className="muted">
            {ticker.sector} {ticker.industry ? `| ${ticker.industry}` : ""}
          </p>
        </div>
        <div className="hero-actions">
          <Link to="/" className="chip">
            Back to dashboard
          </Link>
        </div>
      </section>

      <section className="score-row">
        <ScoreCard label="Benefit" value={ticker.benefit_score.toFixed(1)} tone="positive" />
        <ScoreCard label="Risk" value={ticker.risk_score.toFixed(1)} tone="warning" />
        <ScoreCard label="Confidence" value={ticker.confidence_score.toFixed(1)} tone="neutral" />
        <ScoreCard label="News Sentiment" value={ticker.news_sentiment_score.toFixed(1)} tone="positive" />
      </section>

      <PriceChart series={ticker.price_history} />

      <section className="panel details-grid">
        <article>
          <h3>Quant Summary</h3>
          <p>{ticker.quant_summary}</p>
          <ul className="bullet-list">
            <li>1M return: {formatPercent(returns["1m"])}</li>
            <li>3M return: {formatPercent(returns["3m"])}</li>
            <li>6M return: {formatPercent(returns["6m"])}</li>
            <li>1Y return: {formatPercent(returns["1y"])}</li>
            <li>Beta: {formatNumber(ticker.quant_metrics.beta)}</li>
            <li>RSI14: {formatNumber(ticker.quant_metrics.rsi_14)}</li>
          </ul>
        </article>

        <article>
          <h3>Qualitative Summary</h3>
          <p>{ticker.qualitative_summary}</p>
          <h4>Positive Factors</h4>
          <ul className="bullet-list">
            {ticker.key_positive_factors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h4>Negative Factors</h4>
          <ul className="bullet-list">
            {ticker.key_negative_factors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>

      <section className="panel details-grid">
        <article>
          <h3>Monitoring Triggers</h3>
          <ul className="bullet-list">
            {ticker.monitoring_triggers.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h4>View</h4>
          <p>
            {ticker.investment_view} | {ticker.time_horizon}
          </p>
        </article>

        <article>
          <h3>Final Advice</h3>
          <p>{ticker.short_advice}</p>
          <h4>Sources</h4>
          <ul className="bullet-list">
            {ticker.sources_used.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </article>
      </section>
    </div>
  );
}
