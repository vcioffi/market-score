import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { BasketCard } from "../components/BasketCard";
import { LoadingState } from "../components/LoadingState";
import { RankingTable } from "../components/RankingTable";
import { ScoreCard } from "../components/ScoreCard";
import { TickerSearch } from "../components/TickerSearch";
import { Tooltip } from "../components/Tooltip";
import { getFailedTickers, getMacroLatest, getTickers, getWeeklySummaryLatest, retryMacro, retryTicker } from "../services/api";
import type { FailedTicker, MacroAnalysis, TickerLight, WeeklySummary } from "../types/api";
import { T } from "../utils/tooltips";

function regimeBadgeClass(regime: string): string {
  if (regime === "risk-on") return "badge badge-positive";
  if (regime === "risk-off") return "badge badge-negative";
  return "badge badge-neutral";
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
}

function fmtVal(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

interface FailedTickersPanelProps {
  runDate: string | undefined;
}

function FailedTickersPanel({ runDate }: FailedTickersPanelProps) {
  const [failedTickers, setFailedTickers] = useState<FailedTicker[]>([]);
  const [retrying, setRetrying] = useState<Record<string, boolean>>({});
  const [retryErrors, setRetryErrors] = useState<Record<string, string>>({});
  const [retryingMacro, setRetryingMacro] = useState(false);
  const [macroRetryError, setMacroRetryError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await getFailedTickers(runDate);
      setFailedTickers(res.failed_tickers);
    } catch {
      // no failed tickers file yet — normal on first run
    }
  }, [runDate]);

  useEffect(() => {
    load();
  }, [load]);

  if (failedTickers.length === 0) return null;

  const tickerErrors = failedTickers.filter((t) => t.stage !== "macro");
  const macroErrors = failedTickers.filter((t) => t.stage === "macro");

  async function handleRetry(symbol: string) {
    setRetrying((prev) => ({ ...prev, [symbol]: true }));
    setRetryErrors((prev) => { const next = { ...prev }; delete next[symbol]; return next; });
    try {
      await retryTicker(symbol, runDate);
      setFailedTickers((prev) => prev.filter((t) => t.symbol !== symbol));
    } catch (err) {
      setRetryErrors((prev) => ({ ...prev, [symbol]: (err as Error).message }));
    } finally {
      setRetrying((prev) => ({ ...prev, [symbol]: false }));
    }
  }

  async function handleRetryMacro() {
    setRetryingMacro(true);
    setMacroRetryError(null);
    try {
      await retryMacro(runDate);
      setFailedTickers((prev) => prev.filter((t) => t.stage !== "macro"));
    } catch (err) {
      setMacroRetryError((err as Error).message);
    } finally {
      setRetryingMacro(false);
    }
  }

  return (
    <section className="panel failed-tickers-panel">
      <div className="panel-header">
        <h3>Errori di caricamento dati</h3>
        <span className="badge badge-negative">{failedTickers.length} falliti</span>
      </div>

      {macroErrors.length > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          <div className="failed-ticker-row">
            <div className="failed-ticker-info">
              <span className="ticker-symbol">Analisi Macro</span>
              <span className="failed-ticker-stage muted small">macro — {macroErrors.length} indicatori non scaricati</span>
              <span className="failed-ticker-error muted small" title={macroErrors[0].error}>
                {macroErrors[0].error.length > 80 ? macroErrors[0].error.slice(0, 80) + "…" : macroErrors[0].error}
              </span>
              {macroRetryError && (
                <span className="small" style={{ color: "var(--color-negative)" }}>{macroRetryError}</span>
              )}
            </div>
            <button className="btn-retry" onClick={handleRetryMacro} disabled={retryingMacro}>
              {retryingMacro ? "..." : "Riprova macro"}
            </button>
          </div>
        </div>
      )}

      {tickerErrors.length > 0 && (
        <>
          <p className="muted small" style={{ marginBottom: "0.5rem" }}>
            Ticker non scaricati — riprova singolarmente:
          </p>
          <div className="failed-tickers-list">
            {tickerErrors.map((t) => (
              <div key={t.symbol} className="failed-ticker-row">
                <div className="failed-ticker-info">
                  <span className="ticker-symbol">{t.symbol}</span>
                  <span className="failed-ticker-stage muted small">{t.stage}</span>
                  <span className="failed-ticker-error muted small" title={t.error}>
                    {t.error.length > 80 ? t.error.slice(0, 80) + "…" : t.error}
                  </span>
                  {retryErrors[t.symbol] && (
                    <span className="small" style={{ color: "var(--color-negative)" }}>
                      {retryErrors[t.symbol]}
                    </span>
                  )}
                </div>
                <button
                  className="btn-retry"
                  onClick={() => handleRetry(t.symbol)}
                  disabled={retrying[t.symbol]}
                >
                  {retrying[t.symbol] ? "..." : "Riprova"}
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function MacroPanel({ macro }: { macro: MacroAnalysis }) {
  const coreSymbols = ["^VIX", "^GSPC", "^IXIC", "^TNX", "DX-Y.NYB", "GC=F", "CL=F"];
  const coreIndicators = macro.indicators.filter((i) => coreSymbols.includes(i.symbol));
  const sectorEntries = Object.entries(macro.sector_performance).sort((a, b) => b[1] - a[1]);

  return (
    <section className="panel macro-panel">
      <div className="panel-header">
        <h3>Analisi Macro</h3>
        <span className={regimeBadgeClass(macro.macro_regime)}>
          <Tooltip text={T.macroRegime}>{macro.macro_regime}</Tooltip>
        </span>
      </div>

      <div className="macro-scores-row">
        <ScoreCard
          label="Score Macro"
          value={macro.macro_score.toFixed(1)}
          tone={macro.macro_score >= 55 ? "positive" : macro.macro_score >= 40 ? "neutral" : "warning"}
          tooltip={T.macroScore}
        />
        <ScoreCard
          label="Ampiezza"
          value={macro.market_breadth}
          tone={macro.market_breadth === "expanding" ? "positive" : macro.market_breadth === "contracting" ? "warning" : "neutral"}
          tooltip={T.breadth}
        />
        {macro.vix_level != null && (
          <ScoreCard
            label="VIX"
            value={macro.vix_level.toFixed(1)}
            tone={macro.vix_level < 15 ? "positive" : macro.vix_level < 25 ? "neutral" : "warning"}
            tooltip={T.vix}
          />
        )}
        {macro.yield_curve_spread != null && (
          <ScoreCard
            label="Curva Rendimenti"
            value={`${macro.yield_curve_spread >= 0 ? "+" : ""}${macro.yield_curve_spread.toFixed(2)}pp`}
            tone={macro.yield_curve_spread >= 0.5 ? "positive" : macro.yield_curve_spread >= 0 ? "neutral" : "warning"}
            tooltip={T.yieldCurve}
          />
        )}
      </div>

      {coreIndicators.length > 0 && (
        <div className="macro-indicators-table">
          <table>
            <thead>
              <tr>
                <th>Indicatore</th>
                <th>Valore</th>
                <th>1G</th>
                <th>1M</th>
                <th>3M</th>
              </tr>
            </thead>
            <tbody>
              {coreIndicators.map((ind) => (
                <tr key={ind.symbol}>
                  <td>{ind.name}</td>
                  <td>{fmtVal(ind.current_value)}</td>
                  <td className={ind.change_1d != null && ind.change_1d >= 0 ? "positive" : "negative"}>{fmtPct(ind.change_1d)}</td>
                  <td className={ind.change_1m != null && ind.change_1m >= 0 ? "positive" : "negative"}>{fmtPct(ind.change_1m)}</td>
                  <td className={ind.change_3m != null && ind.change_3m >= 0 ? "positive" : "negative"}>{fmtPct(ind.change_3m)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sectorEntries.length > 0 && (
        <div className="macro-sector-perf">
          <h4>Performance Settoriale (1M)</h4>
          <div className="sector-perf-grid">
            {sectorEntries.map(([sector, perf]) => (
              <div key={sector} className={`sector-perf-item ${perf >= 0 ? "positive" : "negative"}`}>
                <span className="sector-name">{sector}</span>
                <span className="sector-value">{perf >= 0 ? "+" : ""}{perf.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="macro-themes-risks">
        <div>
          <h4>Temi Chiave</h4>
          <ul className="bullet-list">
            {macro.key_macro_themes.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </div>
        <div>
          <h4>Rischi Macro</h4>
          <ul className="bullet-list">
            {macro.macro_risks.map((r) => <li key={r}>{r}</li>)}
          </ul>
        </div>
      </div>

      {macro.macro_commentary && (
        <div className="macro-commentary">
          <h4>Commento</h4>
          <p className="muted">{macro.macro_commentary}</p>
        </div>
      )}
    </section>
  );
}

interface DashboardPageProps {
  onRunDateChange: (runDate: string | undefined) => void;
}

export function DashboardPage({ onRunDateChange }: DashboardPageProps) {
  const [summary, setSummary] = useState<WeeklySummary | null>(null);
  const [macro, setMacro] = useState<MacroAnalysis | null>(null);
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
        if (!mounted) return;
        setSummary(weekly);
        setTickers(tickerRes.tickers);
        onRunDateChange(weekly.run_date);
        try {
          const macroData = await getMacroLatest();
          if (mounted) setMacro(macroData);
        } catch {
          // analisi macro non ancora disponibile per questa esecuzione
        }
      } catch (loadError) {
        if (!mounted) return;
        setError((loadError as Error).message);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();
    return () => { mounted = false; };
  }, [onRunDateChange]);

  const sectors = useMemo(() => {
    if (!summary) return ["All"];
    const unique = Array.from(new Set(summary.ranking.map((item) => item.sector))).sort();
    return ["All", ...unique];
  }, [summary]);

  const filteredTickers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return tickers.filter((item) => {
      if (!normalized) return true;
      return (
        item.symbol.toLowerCase().includes(normalized) ||
        item.company_name.toLowerCase().includes(normalized)
      );
    });
  }, [query, tickers]);

  if (loading) return <LoadingState text="Caricamento classifica settimanale..." />;
  if (error) return <div className="error-box">{error}</div>;
  if (!summary) return <div className="error-box">Nessun riepilogo settimanale disponibile.</div>;

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
          <p className="eyebrow">Panoramica Settimanale</p>
          <h2>{top1 ? `${top1.ticker} guida la classifica` : "Classifica pronta"}</h2>
          <p className="muted">Temi principali e portafogli consigliati generati da analisi quantitativa e qualitativa.</p>
        </div>
        <div className="hero-metrics">
          <ScoreCard label="Top Ticker" value={top1?.ticker ?? "-"} tone="positive" />
          <ScoreCard label="Beneficio Medio" value={avgBenefit.toFixed(1)} tone="positive" tooltip={T.benefit} />
          <ScoreCard label="Rischio Medio" value={avgRisk.toFixed(1)} tone="warning" tooltip={T.risk} />
          <ScoreCard label="Universo" value={String(summary.ranking.length)} tone="neutral" />
        </div>
      </section>

      <section className="controls-row">
        <TickerSearch query={query} onChange={setQuery} />
        <select value={sectorFilter} onChange={(event) => setSectorFilter(event.target.value)}>
          {sectors.map((sector) => (
            <option key={sector} value={sector}>{sector}</option>
          ))}
        </select>
      </section>

      <RankingTable items={summary.ranking} sectorFilter={sectorFilter} />

      <div className="side-grid">
        <BasketCard items={summary.recommended_basket} rationale={summary.basket_rationale} />

        <section className="panel">
          <div className="panel-header">
            <h3>Temi Macro</h3>
          </div>
          <ul className="bullet-list">
            {summary.macro_themes.map((theme) => (
              <li key={theme}>{theme}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h3>Lista di Controllo</h3>
          </div>
          <div className="chip-row">
            {summary.watchlist.map((ticker) => (
              <Link key={ticker} className="chip" to={`/ticker/${ticker}`}>{ticker}</Link>
            ))}
          </div>
        </section>
      </div>

      <FailedTickersPanel runDate={summary?.run_date} />

      {macro && <MacroPanel macro={macro} />}

      <section className="panel">
        <div className="panel-header">
          <h3>Cluster Settoriali</h3>
        </div>
        <div className="cluster-grid">
          {sectorClusters.map((cluster) => (
            <article className="cluster-card" key={cluster.sector}>
              <p className="ticker-symbol">{cluster.sector}</p>
              <p className="muted small">Score medio: {cluster.average_composite_score.toFixed(2)}</p>
              <p className="muted small">Rischio medio: {cluster.average_risk_score.toFixed(2)}</p>
              <p className="small">{cluster.symbols.join(", ")}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel details-grid">
        <article>
          <h3>Segnali di Scenario</h3>
          <ul className="bullet-list">
            {scenarioSignals.map((signal) => (
              <li key={signal}>{signal}</li>
            ))}
          </ul>
        </article>
        <article>
          <h3>Relazioni Competitive</h3>
          <ul className="bullet-list">
            {relationships.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h4>Catene di Fornitura</h4>
          <ul className="bullet-list">
            {supplyChainLinks.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Esplora Ticker</h3>
          <span>{filteredTickers.length} risultati</span>
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
