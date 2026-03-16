import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { LoadingState } from "../components/LoadingState";
import { PriceChart } from "../components/PriceChart";
import { ScoreCard } from "../components/ScoreCard";
import { getLiveNews, getLiveQuote, getTicker } from "../services/api";
import type { FundamentalAnalysis, LiveNews, LiveQuote, NewsArticle, PricePoint, TickerAnalysis } from "../types/api";

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

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("it-IT", { day: "2-digit", month: "short", year: "numeric" });
}

function verdictTone(verdict: string): "positive" | "warning" | "neutral" {
  if (verdict === "undervalued") return "positive";
  if (verdict === "overvalued") return "warning";
  return "neutral";
}

function verdictLabel(verdict: string): string {
  if (verdict === "undervalued") return "Sottovalutato";
  if (verdict === "overvalued") return "Sopravvalutato";
  if (verdict === "fairly_valued") return "Fairly Valued";
  return verdict;
}

function FundamentalSection({ fa, fundamentals }: { fa: FundamentalAnalysis; fundamentals: Record<string, unknown> }) {
  function fmt(v: unknown, decimals = 2): string {
    if (v == null || typeof v !== "number") return "n/a";
    return v.toFixed(decimals);
  }
  function fmtPct(v: unknown): string {
    if (v == null || typeof v !== "number") return "n/a";
    return `${(v * 100).toFixed(1)}%`;
  }
  function fmtPrice(v: unknown): string {
    if (v == null || typeof v !== "number") return "n/a";
    return `$${v.toFixed(2)}`;
  }
  function fmtMoS(v: unknown): string {
    if (v == null || typeof v !== "number") return "n/a";
    return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
  }

  const metrics = [
    { label: "ROE", value: fmtPct(fundamentals.roe) },
    { label: "P/E", value: fmt(fundamentals.pe) },
    { label: "P/B", value: fmt(fundamentals.pb_ratio) },
    { label: "Current Ratio", value: fmt(fundamentals.current_ratio) },
    { label: "Quick Ratio", value: fmt(fundamentals.quick_ratio) },
    { label: "D/E", value: fmt(fundamentals.debt_to_equity) },
    { label: "EPS", value: fmtPrice(fundamentals.trailing_eps) },
    { label: "Graham Number", value: fmtPrice(fundamentals.graham_number) },
    { label: "Margin of Safety", value: fmtMoS(fundamentals.margin_of_safety) },
    { label: "Dividend Yield", value: fmtPct(fundamentals.dividend_yield) },
    { label: "Op. Margin", value: fmtPct(fundamentals.operating_margin) },
    { label: "Rev. Growth", value: fmtPct(fundamentals.revenue_growth) },
  ];

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Analisi Fondamentale</h3>
        <span className={`badge badge-${verdictTone(fa.fundamental_verdict)}`}>
          {verdictLabel(fa.fundamental_verdict)}
        </span>
      </div>

      {/* Fundamental score + key metrics grid */}
      <div className="score-row" style={{ marginBottom: "1rem" }}>
        <ScoreCard label="Fundamental Score" value={fa.fundamental_score.toFixed(1)} tone={verdictTone(fa.fundamental_verdict)} />
      </div>

      <div className="fund-metrics-grid">
        {metrics.map(({ label, value }) => (
          <div key={label} className="fund-metric">
            <span className="fund-metric-label muted small">{label}</span>
            <span className="fund-metric-value">{value}</span>
          </div>
        ))}
      </div>

      {/* Qualitative assessments */}
      <div className="details-grid" style={{ marginTop: "1.25rem" }}>
        <article>
          <h4>Moat / Vantaggio Competitivo</h4>
          <p className="small">{fa.moat_assessment}</p>
        </article>
        <article>
          <h4>Qualità del Management</h4>
          <p className="small">{fa.management_quality}</p>
        </article>
        <article>
          <h4>Prospettive di Crescita</h4>
          <p className="small">{fa.growth_prospects}</p>
        </article>
        <article>
          <h4>Solidità Finanziaria</h4>
          <p className="small">{fa.financial_health_summary}</p>
        </article>
      </div>

      <div style={{ marginTop: "1rem" }}>
        <h4>Fair Value (Graham)</h4>
        <p className="small">{fa.fair_value_assessment}</p>
      </div>

      {/* Strengths & Concerns */}
      <div className="details-grid" style={{ marginTop: "1rem" }}>
        {fa.key_strengths.length > 0 && (
          <article>
            <h4>Punti di Forza</h4>
            <ul className="bullet-list">
              {fa.key_strengths.map((s) => <li key={s}>{s}</li>)}
            </ul>
          </article>
        )}
        {fa.key_concerns.length > 0 && (
          <article>
            <h4>Rischi Fondamentali</h4>
            <ul className="bullet-list">
              {fa.key_concerns.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </article>
        )}
      </div>
    </section>
  );
}

function NewsSection({ news }: { news: LiveNews }) {
  if (!news.articles.length) {
    return null;
  }
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Ultime news — {news.symbol}</h3>
        <span className="muted small">{news.articles.length} articoli</span>
      </div>
      <ul className="news-list">
        {news.articles.map((art: NewsArticle) => (
          <li key={art.url} className="news-item">
            <a href={art.url} target="_blank" rel="noopener noreferrer" className="news-title">
              {art.title}
            </a>
            <div className="news-meta">
              <span>{art.source}</span>
              {art.published_at && <span>{formatDate(art.published_at)}</span>}
            </div>
            {art.summary && art.summary !== art.title && (
              <p className="news-summary muted small">{art.summary}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function LiveQuoteSection({ quote }: { quote: LiveQuote }) {
  return (
    <section className="score-row">
      {quote.current_price != null && (
        <ScoreCard label="Prezzo" value={`$${quote.current_price.toFixed(2)}`} tone="neutral" />
      )}
      <ScoreCard
        label="1 giorno"
        value={fmtPct(quote.change_1d)}
        tone={quote.change_1d == null ? "neutral" : quote.change_1d >= 0 ? "positive" : "warning"}
      />
      <ScoreCard
        label="1 mese"
        value={fmtPct(quote.change_1m)}
        tone={quote.change_1m == null ? "neutral" : quote.change_1m >= 0 ? "positive" : "warning"}
      />
      <ScoreCard
        label="3 mesi"
        value={fmtPct(quote.change_3m)}
        tone={quote.change_3m == null ? "neutral" : quote.change_3m >= 0 ? "positive" : "warning"}
      />
    </section>
  );
}

export function TickerDetailPage() {
  const { symbol } = useParams();
  const [ticker, setTicker] = useState<TickerAnalysis | null>(null);
  const [liveQuote, setLiveQuote] = useState<LiveQuote | null>(null);
  const [liveNews, setLiveNews] = useState<LiveNews | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!symbol) return;
      setLoading(true);
      try {
        // Fetch LLM analysis + live quote + news in parallel
        const [analysisResult, quoteResult, newsResult] = await Promise.allSettled([
          getTicker(symbol),
          getLiveQuote(symbol),
          getLiveNews(symbol),
        ]);

        if (!mounted) return;

        if (analysisResult.status === "fulfilled") {
          setTicker(analysisResult.value);
        }
        // If both analysis and live quote fail, show error
        if (analysisResult.status === "rejected" && quoteResult.status === "rejected") {
          setError(`Simbolo "${symbol.toUpperCase()}" non trovato o backend non raggiungibile.`);
        }
        if (quoteResult.status === "fulfilled") setLiveQuote(quoteResult.value);
        if (newsResult.status === "fulfilled") setLiveNews(newsResult.value);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();
    return () => { mounted = false; };
  }, [symbol]);

  const returns = useMemo(() => {
    if (!ticker) return {};
    return (ticker.quant_metrics.returns as Record<string, unknown>) || {};
  }, [ticker]);

  // Prefer stored price history from analysis; fall back to live quote
  const priceHistory: PricePoint[] = ticker?.price_history?.length
    ? ticker.price_history
    : liveQuote?.price_history ?? [];

  if (loading) {
    return <LoadingState text="Caricamento dati..." />;
  }

  if (error) {
    return <div className="error-box">{error}</div>;
  }

  const displaySymbol = symbol?.toUpperCase() ?? "";
  const displayName = ticker?.company_name ?? displaySymbol;

  return (
    <div className="page-grid">
      <section className="hero compact">
        <div>
          <p className="eyebrow">Ticker Detail</p>
          <h2>
            {displayName} <span className="muted">({displaySymbol})</span>
          </h2>
          {ticker && (
            <p className="muted">
              {ticker.sector} {ticker.industry ? `| ${ticker.industry}` : ""}
            </p>
          )}
          {!ticker && liveQuote && (
            <p className="muted small">Dati live via yfinance — analisi LLM non disponibile per questo simbolo</p>
          )}
        </div>
        <div className="hero-actions">
          <Link to="/" className="chip">
            Back to dashboard
          </Link>
        </div>
      </section>

      {/* LLM analysis scores — only when available */}
      {ticker && (
        <section className="score-row">
          <ScoreCard label="Benefit" value={ticker.benefit_score.toFixed(1)} tone="positive" />
          <ScoreCard label="Risk" value={ticker.risk_score.toFixed(1)} tone="warning" />
          <ScoreCard label="Confidence" value={ticker.confidence_score.toFixed(1)} tone="neutral" />
          <ScoreCard label="News Sentiment" value={ticker.news_sentiment_score.toFixed(1)} tone="positive" />
        </section>
      )}

      {/* Live quote scores — always shown */}
      {liveQuote && <LiveQuoteSection quote={liveQuote} />}

      {/* Price chart — from analysis or live quote */}
      {priceHistory.length > 0 && <PriceChart series={priceHistory} />}

      {/* LLM analysis details — only when available */}
      {ticker && (
        <>
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

          {/* Fundamental analysis — shown when available */}
          {ticker.fundamental_analysis && (
            <FundamentalSection fa={ticker.fundamental_analysis} fundamentals={ticker.fundamentals} />
          )}

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
        </>
      )}

      {/* Live news — always shown when available */}
      {liveNews && <NewsSection news={liveNews} />}
    </div>
  );
}
