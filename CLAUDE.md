# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Market Score** is an AI-assisted financial research platform that runs a multi-stage pipeline to analyze ~100 stock tickers: fetching market data via yfinance, computing quantitative/fundamental metrics, gathering news, calling OpenAI for structured analysis, and serving results via a FastAPI backend to a React dashboard.

## Development Commands

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# or with dev extras:
pip install -e ".[dev]"
```

### Backend: Run the Pipeline

```bash
cd backend
# Dry run (no LLM calls, uses deterministic fallback)
python scripts/run_all.py

# Static analysis (real market data + news, zero LLM cost)
python scripts/run_all.py --static

# Live with batch mode (24h OpenAI batch queue, cost-optimized)
python scripts/run_all.py --live

# Live with direct/synchronous LLM calls (OpenAI, Groq, Ollama, Gemini)
python scripts/run_all.py --live-no-batch --symbols AAPL,MSFT

# With OpenAI web search for news
python scripts/run_all.py --live-no-batch --openai-news-research --symbols NVDA

# Skip news pipeline (reuse saved news context from disk)
python scripts/run_all.py --live --skip-news --symbols AAPL,MSFT

# LLM-only (skip market data, metrics, news — run only LLM on saved data)
python scripts/run_all.py --live --llm-only --symbols AAPL,MSFT

# Run individual pipeline stages
python scripts/run_market_data.py --period 3y
python scripts/run_metrics.py
python scripts/run_news_context.py
python scripts/run_llm_ticker_analysis.py --live
python scripts/run_single_ticker.py AAPL --live
```

### Backend: API Server

```bash
cd backend
python scripts/run_api.py --host 0.0.0.0 --port 8000 --reload
```

### Backend: Tests & Linting

```bash
cd backend
pytest -q               # run tests
pytest -q --cov         # with coverage
ruff check .            # lint
ruff check . --fix      # auto-fix lint issues
```

### Frontend

```bash
cd webapp
npm install
npm run dev      # dev server at http://localhost:5173, proxies /api to backend
npm run build    # production build
npm run preview
```

### Start Everything

```bash
./start.sh           # starts both backend + webapp
./start-backend.sh   # backend only
./start-webapp.sh    # frontend only
```

## Architecture

### Data Pipeline Flow

```
run_all.py → FullPipeline.run_all()
  1. MarketDataPipeline   — yfinance → local CSV cache
  2. MetricsPipeline      — quant (RSI, Sharpe, beta, drawdown) + fundamental (P/E, margins)
  3. NewsPipeline         — Yahoo Finance or OpenAI web search
  4. TickerAnalysisPipeline — OpenAI batch or direct → TickerAnalysis JSON
  5. WeeklySummaryPipeline  — deterministic ranking → optional LLM commentary
  6. MacroPipeline          — VIX, yield curve, sectors → MacroAnalysis JSON
```

Outputs land in `backend/data/outputs/YYYY-MM-DD/` (gitignored):
- `{SYMBOL}.json` — per-ticker `TickerAnalysis`
- `weekly_summary.json` — rankings, basket recommendations, sector clusters
- `macro_analysis.json` — macro conditions

### Backend Structure (`backend/src/`)

| Package | Responsibility |
|---|---|
| `api/` | FastAPI app (`app.py`) + response models |
| `llm/` | `pipeline.py` (orchestrates LLM calls), `batch.py` (OpenAI Batch API), `prompts.py`, `schemas.py` (Pydantic models) |
| `pipelines/` | One file per stage + `run_all_pipeline.py` |
| `market_data/` | yfinance client with TTL-based local cache |
| `metrics/` | Quantitative + fundamental metric calculators |
| `news/` | Pluggable providers: Yahoo, OpenAI research, mock |
| `storage/` | `JsonStorage` for reading/writing output JSON files |
| `tickers/` | `TickerProfile` model + repository loading from `config/tickers.json` |
| `config/` | `pydantic-settings`-based settings; all env vars are prefixed `MARKET_SCORE_` |
| `macro/` | Macroeconomic data fetching and analysis |

### Frontend Structure (`webapp/src/`)

- `pages/` — `DashboardPage.tsx` (macro panel + ranking table + basket), `TickerDetailPage.tsx` (charts + live data)
- `components/` — Reusable UI components (RankingTable, ScoreCard, BasketCard, etc.)
- `services/api.ts` — All HTTP calls to backend
- `types/api.ts` — TypeScript interfaces mirroring backend Pydantic schemas

Vite proxies `/api` to `http://localhost:8000`.

### Key Configuration

- **`backend/config/tickers.json`** — list of ~100 tickers with symbol, name, sector, industry, market, peers
- **`.env`** (from `.env.example`) — all runtime config; key vars:
  - `MARKET_SCORE_LLM_BASE_URL` — URL of the LLM backend (Ollama, Groq, Gemini, or omit for OpenAI)
  - `MARKET_SCORE_LLM_API_KEY` — API key for the active LLM backend
  - `MARKET_SCORE_LLM_MODEL` — model name (overrides OpenAI defaults when set)
  - `MARKET_SCORE_OPENAI_API_KEY` — OpenAI key (legacy, used if `LLM_API_KEY` is not set)
  - `MARKET_SCORE_DRY_RUN=true` — default; set `false` to enable live LLM calls
  - `MARKET_SCORE_OPENAI_USE_BATCH=false` — set `true` to use OpenAI Batch API (24h queue)
  - `MARKET_SCORE_TIMEZONE=Europe/Rome`

### LLM Modes

1. **Dry run** (default) — deterministic fallback, zero cost, no API key needed
2. **Static** (`--static`) — rule-based `StaticAnalysisEngine`, real market data + news, zero LLM calls
3. **Batch mode** (`--live`) — submits to OpenAI Batch API, 24h window, ~50% cheaper
4. **Direct mode** (`--live-no-batch`) — synchronous LLM calls (OpenAI/Groq/Ollama/Gemini), results immediately
5. **News research** (`--openai-news-research`) — uses OpenAI web search for news instead of Yahoo Finance

### API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/runs` | All run dates |
| GET | `/api/runs/latest` | Latest run metadata |
| GET | `/api/tickers` | All ticker scores (latest or `?date=YYYY-MM-DD`) |
| GET | `/api/ticker/{symbol}` | Detailed ticker analysis |
| GET | `/api/weekly-summary/latest` | Weekly summary with rankings |
| GET | `/api/macro/latest` | Macro analysis |
| GET | `/api/live/quote/{symbol}` | Real-time price |
| GET | `/api/live/news/{symbol}` | Real-time news |
| POST | `/api/run-analysis` | Trigger full pipeline |
| POST | `/api/run-single-ticker/{symbol}` | Run one ticker |
