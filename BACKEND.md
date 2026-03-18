# Market Score — Documentazione Tecnica Backend

> Guida tecnica completa dell'architettura, dei moduli, dei flussi di dati e delle API del backend.

---

## Indice

1. [Panoramica architetturale](#1-panoramica-architetturale)
2. [Struttura delle directory](#2-struttura-delle-directory)
3. [Configurazione (Settings)](#3-configurazione-settings)
4. [Pipeline di elaborazione](#4-pipeline-di-elaborazione)
5. [Motori di analisi LLM](#5-motori-di-analisi-llm)
6. [Motore di analisi statica](#6-motore-di-analisi-statica)
7. [Batch management (OpenAI)](#7-batch-management-openai)
8. [Market Data](#8-market-data)
9. [Metriche quantitative e fondamentali](#9-metriche-quantitative-e-fondamentali)
10. [News](#10-news)
11. [Macro](#11-macro)
12. [Portfolio ranking](#12-portfolio-ranking)
13. [Storage](#13-storage)
14. [Tickers](#14-tickers)
15. [Schemi Pydantic](#15-schemi-pydantic)
16. [API REST](#16-api-rest)
17. [Script CLI](#17-script-cli)
18. [Dipendenze](#18-dipendenze)
19. [Flusso dati end-to-end](#19-flusso-dati-end-to-end)

---

## 1. Panoramica architetturale

Market Score è una piattaforma di ricerca finanziaria AI-assistita. Il backend è un'applicazione Python che:

1. **Acquisisce** dati di mercato (prezzi OHLCV, fondamentali) via yfinance
2. **Calcola** metriche quantitative (RSI, Sharpe, beta, drawdown) e fondamentali (Graham Number, margin of safety)
3. **Raccoglie** news da Yahoo Finance (o ricerca web via OpenAI)
4. **Analizza** ogni ticker tramite LLM (OpenAI / Ollama / Groq / Gemini) **oppure** motore deterministico statico
5. **Genera** un riepilogo settimanale con ranking, basket raccomandato e analisi macro
6. **Espone** i risultati tramite API FastAPI consumata dal frontend React

### Modalità operative

| Modalità | `dry_run` | `analysis_mode` | LLM | Costo |
|---|---|---|---|---|
| Dry-run (default) | `true` | `"llm"` | No (fallback deterministico) | Zero |
| Static | `false` | `"static"` | No (engine rule-based) | Zero |
| LLM live | `false` | `"llm"` | Sì (OpenAI/Groq/Ollama) | A consumo |

---

## 2. Struttura delle directory

```
backend/
├── config/
│   ├── tickers.json               # Universe dei ticker (~100 simboli)
│   └── schemas/                   # JSON Schema esportati (generati da export_schemas.py)
├── data/                          # Generato a runtime (gitignored)
│   ├── raw/
│   │   └── {YYYY-MM-DD}/
│   │       ├── market_data/{SYMBOL}.csv    # Storia OHLCV
│   │       └── fundamentals/{SYMBOL}.json  # Dati fondamentali raw
│   ├── processed/
│   │   └── {YYYY-MM-DD}/
│   │       ├── metrics/{SYMBOL}.json       # Metriche calcolate
│   │       ├── news/{SYMBOL}.json          # Contesto news
│   │       └── llm/metadata.json           # Metadata pipeline (batch IDs, ecc.)
│   └── outputs/
│       └── {YYYY-MM-DD}/
│           ├── {SYMBOL}.json               # TickerAnalysis finale
│           ├── weekly_summary.json         # WeeklySummary
│           └── macro_analysis.json         # MacroAnalysis
├── scripts/                       # Entry point CLI
│   ├── run_all.py                 # Pipeline completa
│   ├── run_api.py                 # Server FastAPI
│   ├── run_market_data.py
│   ├── run_metrics.py
│   ├── run_news_context.py
│   ├── run_llm_ticker_analysis.py
│   ├── run_weekly_summary.py
│   ├── run_single_ticker.py
│   ├── run_macro.py
│   ├── sync_openai_batches.py
│   └── export_schemas.py
└── src/
    ├── api/                       # FastAPI app + modelli request/response
    ├── config/                    # Settings (pydantic-settings)
    ├── llm/                       # Motori analisi (LLM, statico, fallback)
    ├── macro/                     # Dati macroeconomici
    ├── market_data/               # Client yfinance + cache
    ├── metrics/                   # Calcolo metriche quantitative e fondamentali
    ├── news/                      # Provider news (Yahoo, OpenAI, mock)
    ├── pipelines/                 # Orchestratori (una classe per stage)
    ├── portfolio/                 # Ranking e costruzione basket
    ├── storage/                   # Lettura/scrittura file JSON/CSV
    ├── tickers/                   # Modello TickerProfile e repository
    └── utils/                     # Logging, retry, date utils
```

---

## 3. Configurazione (Settings)

**File:** `src/config/settings.py`
**Classe:** `Settings(BaseSettings)` — caricata da variabili d'ambiente con prefisso `MARKET_SCORE_`
**Singleton:** `get_settings()` — decorato con `@lru_cache(maxsize=1)`

### Core

| Variabile d'ambiente | Tipo | Default | Descrizione |
|---|---|---|---|
| `MARKET_SCORE_TIMEZONE` | `str` | `"Europe/Rome"` | Timezone per date run |
| `MARKET_SCORE_LOG_LEVEL` | `str` | `"INFO"` | Livello logging Python |
| `MARKET_SCORE_DRY_RUN` | `bool` | `true` | Se true, usa fallback deterministico (zero costo) |
| `MARKET_SCORE_ANALYSIS_MODE` | `str` | `"llm"` | `"llm"` o `"static"` |
| `MARKET_SCORE_MAX_TICKERS_PER_RUN` | `int` | `100` | Limite ticker per esecuzione |

### Market Data

| Variabile | Tipo | Default | Descrizione |
|---|---|---|---|
| `MARKET_SCORE_BENCHMARK_SYMBOL` | `str` | `"SPY"` | Benchmark per beta/correlazione |
| `MARKET_SCORE_DEFAULT_HISTORY_PERIOD` | `str` | `"3y"` | Periodo storia yfinance |
| `MARKET_SCORE_HISTORY_INTERVAL` | `str` | `"1d"` | Frequenza OHLCV |
| `MARKET_SCORE_RISK_FREE_RATE_ANNUAL` | `float` | `0.02` | Tasso risk-free per Sharpe/Sortino |

### News

| Variabile | Tipo | Default | Descrizione |
|---|---|---|---|
| `MARKET_SCORE_MAX_COMPANY_NEWS` | `int` | `3` | Articoli azienda per ticker |
| `MARKET_SCORE_MAX_SECTOR_NEWS` | `int` | `3` | Articoli settore per ticker |
| `MARKET_SCORE_NEWS_WINDOW_DAYS` | `int` | `30` | Finestra temporale news (giorni) |
| `MARKET_SCORE_NEWS_SUMMARY_CHAR_LIMIT` | `int` | `200` | Lunghezza massima summary |
| `MARKET_SCORE_ALLOW_MOCK_NEWS` | `bool` | `true` | Fallback a news mock offline |

### Backend LLM generico (OpenAI-compatibile)

| Variabile | Tipo | Default | Descrizione |
|---|---|---|---|
| `MARKET_SCORE_LLM_BASE_URL` | `str\|None` | `None` | URL endpoint custom (Ollama, Groq, Gemini) |
| `MARKET_SCORE_LLM_API_KEY` | `str\|None` | `None` | Chiave API per endpoint custom |
| `MARKET_SCORE_LLM_MODEL` | `str\|None` | `None` | Nome modello (sovrascrive quelli OpenAI) |
| `MARKET_SCORE_LLM_USE_JSON_SCHEMA` | `bool` | `true` | False per provider senza strict schema (Ollama) |

### OpenAI (legacy, backward-compatible)

| Variabile | Tipo | Default | Descrizione |
|---|---|---|---|
| `MARKET_SCORE_OPENAI_API_KEY` | `str\|None` | `None` | Chiave API OpenAI |
| `MARKET_SCORE_OPENAI_MODEL_TICKER` | `str` | `"gpt-4o-mini"` | Modello per analisi ticker |
| `MARKET_SCORE_OPENAI_MODEL_WEEKLY` | `str` | `"gpt-4o-mini"` | Modello per weekly/macro |
| `MARKET_SCORE_OPENAI_MODEL_NEWS` | `str` | `"gpt-4o-mini"` | Modello per ricerca news |
| `MARKET_SCORE_OPENAI_USE_BATCH` | `bool` | `true` | Usa Batch API (sconto ~50%) |
| `MARKET_SCORE_OPENAI_COMPLETION_WINDOW` | `str` | `"24h"` | Finestra completamento batch |
| `MARKET_SCORE_OPENAI_POLL_INTERVAL_SECONDS` | `int` | `30` | Frequenza polling batch |
| `MARKET_SCORE_OPENAI_MAX_WAIT_MINUTES` | `int` | `180` | Attesa massima batch |
| `MARKET_SCORE_OPENAI_TICKER_MAX_COMPLETION_TOKENS` | `int` | `3000` | Budget token per ticker |
| `MARKET_SCORE_OPENAI_WEEKLY_MAX_COMPLETION_TOKENS` | `int` | `3000` | Budget token per weekly/macro |
| `MARKET_SCORE_OPENAI_NEWS_MAX_OUTPUT_TOKENS` | `int` | `12000` | Budget token per news research |
| `MARKET_SCORE_OPENAI_NEWS_SEARCH_CONTEXT_SIZE` | `str` | `"medium"` | Dimensione contesto ricerca web |
| `MARKET_SCORE_OPENAI_NEWS_RESEARCH_ENABLED` | `bool` | `false` | Abilita ricerca web news |
| `MARKET_SCORE_OPENAI_NEWS_WORKERS` | `int` | `1` | Worker paralleli per ricerca news |

### Proprietà calcolate

```python
settings.effective_llm_api_key      # llm_api_key or openai_api_key
settings.effective_llm_base_url     # llm_base_url (None = OpenAI default)
settings.effective_llm_model_ticker # llm_model or openai_model_ticker
settings.effective_llm_model_weekly # llm_model or openai_model_weekly
settings.llm_live_mode              # bool — True se LLM backend configurato
```

### Path calcolati

```python
settings.backend_root             # .../backend/
settings.raw_data_dir             # .../backend/data/raw/
settings.processed_data_dir       # .../backend/data/processed/
settings.outputs_data_dir         # .../backend/data/outputs/
settings.ticker_config_path       # .../backend/config/tickers.json
settings.schemas_dir              # .../backend/config/schemas/
settings.openai_batch_registry_path  # .../processed/openai_batches_registry.json
```

---

## 4. Pipeline di elaborazione

**File:** `src/pipelines/run_all_pipeline.py`

### Flusso completo

```
FullPipeline.run_all()
  │
  ├─ 1. MarketDataPipeline.run()      → raw/market_data/ + raw/fundamentals/
  ├─ 2. MetricsPipeline.run()         → processed/metrics/
  ├─ 3. NewsPipeline.run()            → processed/news/
  ├─ 4. TickerAnalysisPipeline.run()  → outputs/{SYMBOL}.json
  ├─ 5. WeeklySummaryPipeline.run()   → outputs/weekly_summary.json
  └─ 6. MacroPipeline.run()           → outputs/macro_analysis.json
```

### 4.1 MarketDataPipeline

**File:** `src/pipelines/market_data_pipeline.py`

```python
def run(run_date, period=None, force_refresh=False, symbols=None) -> dict
```

**Logica:**
1. Carica `TickerProfile` dal repository, filtra per `symbols` se specificato
2. Scarica storia benchmark (SPY) — usata per beta/correlazione
3. Per ogni ticker:
   - `MarketDataClient.fetch_history()` → DataFrame OHLCV (TTL cache 24h)
   - `MarketDataClient.fetch_fundamentals()` → dict con 20+ ratios (TTL cache 72h)
   - Salva in storage
   - Se `ValueError("No market data returned")` → ticker delisted, rimuove da `tickers.json`
4. Ritorna: `{run_date, processed, failed, fallback_symbols, removed_symbols, benchmark, period}`

### 4.2 MetricsPipeline

**File:** `src/pipelines/metrics_pipeline.py`

```python
def run(run_date, symbols=None) -> dict
```

**Logica:**
1. Carica storia OHLCV + benchmark + fondamentali raw dallo storage
2. Chiama `build_metrics_bundle()` → calcola tutte le metriche
3. Salva bundle in `processed/{run_date}/metrics/{SYMBOL}.json`
4. Ritorna: `{run_date, processed, failed}`

### 4.3 NewsPipeline

**File:** `src/pipelines/news_pipeline.py`

```python
def run(run_date, symbols=None, max_workers=1) -> dict
```

**Logica:**
1. Per ogni ticker, chiama `NewsContextService.build_context()`
2. Se `openai_news_research_enabled` e `llm_live_mode`:
   - Tenta ricerca web via `OpenAINewsResearchService`
   - Se fallisce: fallback a Yahoo Finance
3. Altrimenti: Yahoo Finance provider
4. Se entrambi falliscono e `allow_mock_news`: usa `MockNewsProvider`
5. Filtra per `news_window_days`, deduplicatura, truncating summary
6. Salva in `processed/{run_date}/news/{SYMBOL}.json`
7. Ritorna: `{run_date, processed, failed, provider_mode, openai_researched, openai_fallback, openai_errors}`

### 4.4 TickerAnalysisPipeline

**File:** `src/pipelines/ticker_analysis_pipeline.py`

```python
def run(run_date, wait_for_batch=False, symbols=None) -> dict
```

**Logica:**
1. Carica metrics + news per ogni ticker → lista di `TickerLLMInput`
2. Sceglie engine:
   - `settings.analysis_mode == "static"` → `StaticAnalysisEngine`
   - altrimenti → `TickerLLMAnalysisEngine`
3. `engine.run()` ritorna `(dict[symbol→TickerAnalysis], metadata)`
4. Salva ogni ticker **immediatamente** dopo analisi (progress survives Ctrl+C)
5. Ritorna: `{run_date, processed, metadata}`

### 4.5 WeeklySummaryPipeline

**File:** `src/pipelines/weekly_summary_pipeline.py`

```python
def run(run_date, wait_for_batch=True) -> dict
```

**Logica:**
1. Carica tutti i file `*.json` da `outputs/{run_date}/` (esclude `weekly_summary.json` e `macro_analysis.json`)
2. Valida ogni file come `TickerAnalysis`, logga warning per file invalidi
3. `build_weekly_summary()` → ranking deterministico completo
4. `WeeklyLLMEngine.generate_commentary()` → narrativa opzionale (solo highlights)
5. Merge del commento LLM nel WeeklySummary
6. Salva `weekly_summary.json`
7. Ritorna: `{run_date, tickers, has_llm_commentary, llm_metadata}`

### 4.6 MacroPipeline

**File:** `src/pipelines/macro_pipeline.py`

```python
def run(run_date) -> dict
```

**Logica:**
1. `MacroService.fetch_macro_context()` → scarica VIX, yield curve, indici, settori
2. `MacroLLMEngine.generate_analysis()` → analisi LLM o fallback deterministico
3. Merge output LLM con dati raw → `MacroAnalysis`
4. Salva `macro_analysis.json`
5. Ritorna: `{status, run_date, macro_regime, macro_score, indicators_count, llm}`

---

## 5. Motori di analisi LLM

**File:** `src/llm/pipeline.py`

### 5.1 TickerLLMInput (dataclass)

```python
@dataclass
class TickerLLMInput:
    profile: TickerProfile
    metrics_payload: dict       # {quant: {...}, fundamentals: {...}, price_history: [...]}
    news_payload: dict          # {company_news: [...], sector_news: [...], company_sentiment: {...}}

    def to_prompt_payload(self) -> dict:
        # Compatta i dati per il prompt LLM:
        # - arrotonda valori float (3 decimali)
        # - calcola distanze % dalle MA (più utili dei valori assoluti)
        # - include max 3 articoli con title[:80] + summary[:150]
```

### 5.2 TickerLLMAnalysisEngine

Tre percorsi di esecuzione:

```
TickerLLMAnalysisEngine.run()
  │
  ├─ dry_run=True OR no LLM configured
  │    └─ _fallback_map() → build_fallback_ticker_analysis() per ogni ticker
  │
  ├─ not use_batch OR custom base_url
  │    └─ _run_direct()
  │         ├─ OpenAIDirectManager.create_chat_completion() per ogni ticker
  │         ├─ Retry con prompt arricchito se output invalido
  │         └─ Salva immediatamente via callback on_ticker_done()
  │
  └─ use_batch=True AND OpenAI standard
       └─ _run_batch()
            ├─ Scrive JSONL batch file
            ├─ Submits via OpenAI Batch API
            ├─ Registra in OpenAIBatchRegistry
            ├─ Se wait_for_batch: attende completamento (polling ogni poll_interval)
            └─ Scarica + parsa output → merge con dati pipeline
```

**Firma:**
```python
def run(
    inputs: list[TickerLLMInput],
    run_date: str,
    artifacts_dir: Path,
    wait_for_batch: bool = False,
    on_ticker_done: callable = None,
) -> tuple[dict[str, TickerAnalysis], dict]
```

**Retry logic (direct mode):**
- Tentativo 1: richiesta standard
- Se `ValidationError` o `JSONDecodeError`:
  - Se `finish_reason='length'`: retry con `max_tokens * 2` (max 4000)
  - Altrimenti: retry con istruzione aggiuntiva `"Return a single valid JSON object only"`
- Tentativo 2 fallito → ticker usa fallback

### 5.3 WeeklyLLMEngine

```python
def generate_commentary(
    run_date: str,
    deterministic_summary: dict,
    artifacts_dir: Path,
    wait_for_batch: bool = True,
) -> tuple[str | None, dict]
```

**Payload compatto inviato al LLM** (non il ranking completo dei 100 ticker):
- `top_tickers[:10]`, `worst_tickers[-10:]`
- `recommended_basket`, `basket_rationale`
- `sector_clusters`, `macro_themes`, `watchlist`, `systemic_risks`

### 5.4 MacroLLMEngine

```python
def generate_analysis(
    run_date: str,
    macro_context: dict,
    artifacts_dir: Path,
) -> tuple[MacroAnalysis, dict]
```

**Fallback deterministico** (quando dry_run o no LLM):
- Regime da VIX: `<15` → risk-on, `15-25` → transitioning, `>25` → risk-off
- Yield curve: inverted (`<0`) / flat (`0-0.5pp`) / normale (`>0.5pp`)
- Breadth da settori: `≥70%` positivi → expanding, `40-70%` → mixed, `<40%` → contracting
- Macro score: 50 base ± aggiustamenti VIX, spread, performance settori

---

## 6. Motore di analisi statica

**File:** `src/llm/static_engine.py`

**Classe:** `StaticAnalysisEngine` — zero chiamate API, dati reali da yfinance + Yahoo news

```python
def run(inputs: list[TickerLLMInput], **_kwargs) -> tuple[dict[str, TickerAnalysis], dict]
```

### Calcolo dei campi

#### `quant_summary` — narrativa tecnica

Costruisce una stringa leggibile con dati reali:
```
"Price $185.20 | Returns: 1M +3.2% / 3M +8.1% / 1Y +24.6%.
 RSI(14) 62.3 — bullish momentum.
 Price 12.4% above MA50 ($164.50), 18.1% above MA200 ($156.80).
 20d volatility 18.2% (moderate). Max drawdown -23.4%. Sharpe 1.42 (strong). Beta 1.15 (market-correlated)."
```

#### `qualitative_summary` — narrativa news

```
"News: [titolo 1] | [titolo 2] | [titolo 3].
 Sector: [titolo settore 1] | [titolo settore 2].
 Company sentiment 68/100 (bullish) — Strong quarterly earnings beat analyst estimates."
```

#### `key_positive_factors` / `key_negative_factors`

Generati deterministicamente da soglie specifiche:

| Soglia | Fattore positivo | Fattore negativo |
|---|---|---|
| 1Y return > 20% | "Strong 1Y return +X% reflects sustained outperformance" | — |
| 1Y return < -20% | — | "1Y loss of X% raises sustained downtrend concern" |
| RSI 45-68 | "RSI X in healthy zone — momentum without overbought exhaustion" | — |
| RSI > 75 | — | "RSI X overbought — elevated mean-reversion risk" |
| Prezzo > MA200 (+5%) | "Price X% above MA200 confirms long-term uptrend intact" | — |
| ROE > 20% | "ROE X% — high return on equity signals durable competitive advantage" | — |
| D/E > 200% | — | "High leverage D/E X% — interest coverage risk in rising-rate environment" |
| MoS > 25% | "Graham margin of safety X% — trading materially below intrinsic value" | — |
| Breakout signal | "Breakout signal active — price approaching multi-week high" | — |

#### `_compute_scores()` — formula scoring

```python
benefit_score = bound(
    55
    + (ret_1m + ret_3m + ret_1y + momentum) * 30   # momentum
    + (news_sentiment - 50) * 0.25                  # news
    + sharpe * 3                                     # risk-adjusted return
    + fund_delta                                     # fundamentals delta
)

risk_score = bound(
    35
    + vol * 90          # volatility
    + drawdown * 70     # max drawdown
    + (beta - 1) * 8    # systematic risk
    + 12 if RSI > 75    # overbought penalty
    - 6 if RSI < 35     # oversold bonus
)

confidence_score = bound(40 + data_points * 7 + article_count * 2)
```

`fund_delta` è calcolato da: ROE (+max 8), revenue growth (+max 8), operating margin (+max 6), D/E (penalità se >100), margin of safety (±max 8).

#### `investment_view` + `time_horizon` da gap benefit-risk

| Gap | View | Horizon |
|---|---|---|
| > 22 | `"constructive"` | `"6–18 months"` |
| 10–22 | `"selective bullish"` | `"3–12 months"` |
| -5 – 10 | `"neutral"` | `"1–6 months"` |
| < -5 | `"defensive"` | `"short-term caution"` |

#### `monitoring_triggers` — trigger specifici con livelli reali

- Break below MA50 (`$164.50`) on above-average volume
- MA200 (`$156.80`) is key long-term support
- Earnings report: watch guidance revision + beat/miss vs consensus
- Relative performance vs peers (MSFT, GOOGL, META)

#### `fundamental_analysis`

Delegato a `_build_fallback_fundamental_analysis()` (da `fallback.py`):
- Score 0-100 rule-based (ROE, leverage, liquidity, crescita, margini)
- Verdict: `undervalued` / `fairly_valued` / `overvalued` da margin of safety o P/E
- Graham Number = `√(22.5 × EPS × BVPS)` se entrambi > 0
- Margin of Safety = `(graham_num - price) / graham_num × 100`

---

## 7. Batch Management (OpenAI)

**File:** `src/llm/batch.py`

### BatchRequest (dataclass)

```python
@dataclass
class BatchRequest:
    custom_id: str              # es. "2026-03-17:AAPL"
    model: str                  # es. "gpt-4o-mini"
    system_prompt: str
    user_prompt: str
    json_schema_name: str       # es. "ticker_analysis"
    json_schema: dict           # JSON Schema Pydantic
    max_completion_tokens: int | None
    temperature: float | None
```

### OpenAIBatchManager

```python
write_requests_jsonl(requests, target_path) -> Path
    # Scrive file JSONL nel formato OpenAI Batch:
    # {custom_id, method: "POST", url: "/v1/chat/completions", body: {...}}

submit_batch(jsonl_path, metadata=None) -> dict
    # 1. Upload file via client.files.create(purpose="batch")
    # 2. client.batches.create(endpoint="/v1/chat/completions", completion_window="24h")
    # Ritorna batch dict con {id, status, ...}

wait_for_completion(batch_id, max_wait_minutes, poll_seconds) -> dict
    # Poll ogni poll_seconds fino a status in {completed, failed, expired, cancelled}
    # Lancia TimeoutError se supera max_wait_minutes

download_output_lines(output_file_id) -> list[dict]
    # Scarica file JSONL di output → lista di dict per ogni riga
```

### OpenAIDirectManager

```python
def __init__(api_key, base_url=None, use_json_schema=True):
    # base_url: None = OpenAI | "http://localhost:11434/v1" = Ollama | ecc.
    # use_json_schema: False per provider senza strict mode (Ollama)
    effective_key = api_key or "local"   # Ollama non richiede chiave
    self.client = OpenAI(api_key=effective_key, base_url=base_url)

@with_retry(attempts=3, min_wait_seconds=1.0, max_wait_seconds=8.0)
def create_chat_completion(request: BatchRequest) -> dict:
    # response_format: json_schema (strict) or json_object (fallback)
    # Ritorna response.model_dump()
```

### Schema normalizzazione

```python
normalize_openai_json_schema(schema) -> dict
    # OpenAI strict mode richiede:
    # - additionalProperties: false
    # - required: [tutti i campi in properties]
    # Applicato ricorsivamente
```

### Funzioni di estrazione

```python
extract_chat_completion_content(response_payload) -> str
    # response_payload["choices"][0]["message"]["content"]
    # Gestisce content list (blocchi multipli)
    # Lancia ValueError se contenuto vuoto (max_tokens, refusal)

extract_message_content(batch_output_line) -> str
    # batch_line["response"]["body"]["choices"][0]["message"]["content"]
```

### OpenAIBatchRegistry

**File:** `src/llm/registry.py`

Tiene traccia del ciclo di vita dei batch job in `openai_batches_registry.json`.

```python
upsert(entry: dict) -> dict          # Insert o merge per batch_id
update(batch_id, **kwargs) -> dict   # Aggiorna campi specifici
get(batch_id) -> dict | None

list_entries(
    statuses=None,    # filtra per status
    downloaded=None,  # filtra per downloaded=True/False
    run_date=None,    # filtra per run_date
) -> list[dict]      # ordinato per submitted_at
```

**Struttura entry:**
```json
{
  "batch_id": "batch_xxx",
  "pipeline": "ticker_analysis",
  "run_date": "2026-03-17",
  "status": "completed",
  "completion_window": "24h",
  "symbols": ["AAPL", "MSFT", ...],
  "artifacts_dir": ".../.../llm",
  "submitted_at": "2026-03-17T10:00:00Z",
  "downloaded": true,
  "downloaded_at": "2026-03-17T12:34:56Z",
  "parsed_items": 57
}
```

---

## 8. Market Data

**File:** `src/market_data/client.py`

### MarketDataClient

```python
def fetch_history(symbol, period, interval="1d", force_refresh=False, cache_ttl_hours=24) -> pd.DataFrame:
    # Cache in raw_dir/market_data/{symbol}_{period}_{interval}.csv
    # Usa file cached se age < cache_ttl_hours e not force_refresh
    # yfinance.download(symbol, period=period, interval=interval, auto_adjust=False, threads=False)
    # Gestisce MultiIndex columns (da yfinance multi-ticker)
    # Lancia ValueError se DataFrame vuoto → ticker delisted

def fetch_fundamentals(symbol, force_refresh=False, cache_ttl_hours=72) -> dict:
    # Cache in raw_dir/fundamentals/{symbol}.json
    # yf.Ticker(symbol).info → dict (può essere vuoto)
    # Campi chiave: marketCap, revenueGrowth, debtToEquity, grossMargins,
    #   operatingMargins, earningsGrowth, trailingPE, forwardPE,
    #   freeCashflow, returnOnEquity, priceToBook, currentRatio,
    #   quickRatio, bookValue, trailingEps, dividendYield, ebitdaMargins
```

### Mock data

`src/market_data/mock_data.py` — `generate_mock_history(symbol, period)` → DataFrame con dati sintetici, usato come fallback se benchmark fetch fallisce.

---

## 9. Metriche quantitative e fondamentali

**File:** `src/metrics/`

### `build_metrics_bundle(history, benchmark_history, fundamentals, risk_free_rate)` → dict

Ritorna `{quant: {...}, fundamentals: {...}, price_history: [...]}`

### Metriche quantitative — `compute_quant_metrics()`

| Campo | Calcolo |
|---|---|
| `latest_close` | Ultimo prezzo di chiusura |
| `returns.1m` | (close[-1] / close[-22]) - 1 |
| `returns.3m` | (close[-1] / close[-65]) - 1 |
| `returns.1y` | (close[-1] / close[-252]) - 1 |
| `rolling_volatility_20d` | std(daily_returns[-20:]) × √252 |
| `max_drawdown` | min((close / cummax(close)) - 1) |
| `sharpe_ratio` | (mean_ret - rf/252) / std_ret × √252 |
| `sortino_ratio` | Come Sharpe ma usa solo ritorni negativi |
| `rsi_14` | RSI classico a 14 periodi |
| `beta` | cov(ret, bench_ret) / var(bench_ret) |
| `correlation_benchmark` | pearsonr(ret, bench_ret) |
| `moving_averages.ma_20/50/200` | Media mobile semplice |
| `distance_recent_high` | (close[-1] / max(close[-52w])) - 1 |
| `signals.breakout` | close > ma_20 AND close vicino al max 52w |
| `signals.volatility_compression` | Bollinger Bands bandwidth < soglia |

### Metriche fondamentali — `normalize_fundamentals(raw, current_price)`

| Campo | Formula / Fonte |
|---|---|
| `pe` | `trailingPE` da yfinance info |
| `forward_pe` | `forwardPE` |
| `revenue_growth` | `revenueGrowth` |
| `operating_margin` | `operatingMargins` |
| `ebitda_margin` | `ebitdaMargins` |
| `eps_growth` | `earningsGrowth` |
| `roe` | `returnOnEquity` |
| `pb_ratio` | `priceToBook` |
| `debt_to_equity` | `debtToEquity` |
| `current_ratio` | `currentRatio` |
| `book_value_per_share` | `bookValue` |
| `trailing_eps` | `trailingEps` |
| `dividend_yield` | `dividendYield` |
| `graham_number` | `√(22.5 × EPS × BVPS)` se EPS > 0 e BVPS > 0 |
| `margin_of_safety` | `(graham_number - price) / graham_number × 100` |

---

## 10. News

**File:** `src/news/`

### Provider hierarchy

```
NewsContextService.build_context()
  │
  ├─ OpenAI research enabled + llm_live_mode?
  │    └─ OpenAINewsResearchService.build_context()   [web search]
  │         └─ FAIL → fallback ↓
  │
  ├─ YahooFinanceNewsProvider.fetch_company_news()    [yfinance.Ticker.news]
  │   YahooFinanceNewsProvider.fetch_sector_news()
  │    └─ FAIL → fallback ↓
  │
  └─ allow_mock_news?
       └─ MockNewsProvider.fetch_company_news()       [dati sintetici]
```

### NewsArticle (Pydantic model)

```python
class NewsArticle(BaseModel):
    title: str
    url: str
    source: str
    summary: str
    published_at: datetime | None
    related_symbol: str
    category: str   # "company" | "sector"
```

### NewsContext (Pydantic model)

```python
class NewsContext(BaseModel):
    company_news: list[NewsArticle]
    sector_news: list[NewsArticle]
    company_sentiment: dict | None   # {score_0_100, label, rationale}
    sector_sentiment: dict | None
    sources_used: list[str]          # ["yfinance"] | ["openai_web_search"] | ["mock"]
```

### OpenAINewsResearchService

- Usa `client.responses.create()` con tool `web_search` / `web_search_preview`
- Prompt compatto: company name, symbol, sector, peers, window, limiti articoli
- Output: JSON con `company_news`, `sector_news`, `company_sentiment`, `sector_sentiment`
- Retry: 2 tentativi con backoff 1-6s
- `search_context_size`: `"high"` (standard) o `"medium"` (deep-research models)

---

## 11. Macro

**File:** `src/macro/`

### MacroService.fetch_macro_context() → dict

**Indicatori scaricati via yfinance:**

| Simbolo | Nome | Categoria |
|---|---|---|
| `^VIX` | CBOE VIX | volatility |
| `^GSPC` | S&P 500 | market |
| `^IXIC` | NASDAQ Composite | market |
| `^RUT` | Russell 2000 | market |
| `^TNX` | 10Y Treasury Yield | yields |
| `^IRX` | 3M T-Bill Rate | yields |
| `TLT` | iShares 20Y+ Treasury ETF | bonds |
| `HYG` | iShares High Yield ETF | bonds |
| `DX-Y.NYB` | US Dollar Index | currency |
| `GC=F` | Gold Futures | commodity |
| `CL=F` | Crude Oil Futures | commodity |

**ETF settoriali per performance 1M:**

`XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLB, XLU, XLRE, XLC`

**Campi nel context:**
- `indicators: list[MacroIndicator]` — valore corrente + variazioni 1d/1m/3m
- `yield_curve_spread` — 10Y - 3M (spread in punti percentuali)
- `vix_level` — VIX corrente
- `sector_performance: dict[str, float]` — Ritorno 1M per settore

---

## 12. Portfolio ranking

**File:** `src/portfolio/ranking.py`

### Composite score

```python
composite_score = (
    0.45 * benefit_score
  + 0.15 * news_sentiment_score
  + 0.20 * confidence_score
  - 0.30 * risk_score
)
# Range tipico: -50 a +100
```

### Basket construction

1. Prende i top ticker per composite score
2. **Concentration control:** max 2 ticker per settore
3. Peso uguale: `1 / N` per ogni posizione
4. Max 8 posizioni nel basket

### Sector clusters

- Raggruppa per settore → calcola average composite + average risk
- Top 6 ticker per settore (per simboli)
- Ordina cluster per average composite score decrescente

### Watchlist

Ticker con: `benefit_score > 58` AND `risk_score > 52` AND `composite_score > 20`
(opportunità mid-range, non ancora nel basket)

### Systemic risks

- Ticker con `beta > 1.35` → "High-beta cluster"
- Ticker con `volatility > 0.45` → "Elevated volatility cluster"
- Alert se ≥ 8 ticker con metriche elevate

---

## 13. Storage

**File:** `src/storage/json_store.py`

### JsonStorage

```python
# Costruttore
JsonStorage(raw_dir: Path, processed_dir: Path, outputs_dir: Path)

# Market data
save_history(run_date, symbol, history: pd.DataFrame) -> Path
load_history(run_date, symbol) -> pd.DataFrame
save_fundamentals(run_date, symbol, payload: dict) -> Path
load_fundamentals(run_date, symbol) -> dict

# Processed
save_processed_metrics(run_date, symbol, payload: dict) -> Path
load_processed_metrics(run_date, symbol) -> dict
save_news_context(run_date, symbol, payload: dict) -> Path
load_news_context(run_date, symbol) -> dict   # {} se file assente

# Outputs
save_ticker_output(run_date, symbol, payload: dict) -> Path
load_ticker_output(run_date, symbol) -> dict
save_weekly_summary(run_date, payload: dict) -> Path
load_weekly_summary(run_date) -> dict
save_macro_analysis(run_date, payload: dict) -> Path

# Navigation
list_run_dates() -> list[str]         # directory ordinate in outputs/
latest_run_date() -> str | None
list_ticker_output_files(run_date) -> list[Path]
    # Esclude: weekly_summary.json, macro_analysis.json

# Generic
save_json(path: Path, payload) -> None
load_json(path: Path) -> Any
```

---

## 14. Tickers

**File:** `src/tickers/models.py`, `src/tickers/repository.py`

### TickerProfile (Pydantic)

```python
class TickerProfile(BaseModel):
    symbol: str           # Es. "AAPL" (min_length=1)
    company_name: str = ""
    sector: str = "Unknown"
    industry: str = "Unknown"
    market: str = "US"
    peers: list[str] = []  # Simboli peer per confronto
```

### TickerRepository

```python
load_all() -> list[TickerProfile]
load_symbols(limit=None) -> list[TickerProfile]   # Slice primi N
find_by_symbol(symbol) -> TickerProfile | None
remove_symbol(symbol) -> bool   # Rimuove da tickers.json (ticker delisted)
```

### config/tickers.json — struttura

```json
[
  {
    "symbol": "AAPL",
    "company_name": "Apple Inc.",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "market": "US",
    "peers": ["MSFT", "GOOGL", "META", "AMZN"]
  }
]
```

I ticker inclusi per default coprono i principali settori del mercato USA: Technology, Financial Services, Healthcare, Consumer Cyclical, Consumer Defensive, Energy, Industrials, Communication Services, Utilities, Real Estate.

---

## 15. Schemi Pydantic

**File:** `src/llm/schemas.py`

### PricePoint

```python
class PricePoint(BaseModel):
    date: str                    # "YYYY-MM-DD"
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int = 0
```

### FundamentalAnalysisLLM

```python
class FundamentalAnalysisLLM(BaseModel):
    moat_assessment: str              # Moat economico, vantaggi competitivi
    management_quality: str           # Qualità leadership, capital allocation
    growth_prospects: str             # Outlook crescita 3-5 anni
    financial_health_summary: str     # Balance sheet, liquidità, debito
    fair_value_assessment: str        # P/E, P/B, Graham Number, verdict
    fundamental_score: float          # 0-100
    fundamental_verdict: str          # "undervalued" | "fairly_valued" | "overvalued"
    key_strengths: list[str]
    key_concerns: list[str]
```

### TickerAnalysis (schema completo output)

```python
class TickerAnalysis(BaseModel):
    ticker: str
    company_name: str
    sector: str
    industry: str | None = None
    quant_summary: str                # Narrativa tecnica (RSI, MA, vol, Sharpe...)
    qualitative_summary: str          # Narrativa news + sentiment
    key_positive_factors: list[str]
    key_negative_factors: list[str]
    news_sentiment_score: float       # 0-100
    risk_score: float                 # 0-100
    benefit_score: float              # 0-100
    confidence_score: float           # 0-100
    investment_view: str              # "constructive" | "selective bullish" | "neutral" | "defensive"
    time_horizon: str                 # "6–18 months" | ecc.
    monitoring_triggers: list[str]
    short_advice: str
    sources_used: list[str]
    quant_metrics: dict               # Metriche quantitative complete
    fundamentals: dict                # Fondamentali normalizzati
    fundamental_analysis: FundamentalAnalysisLLM | None
    price_history: list[PricePoint]
    timestamp: str                    # ISO UTC
```

### WeeklySummary

```python
class WeeklySummary(BaseModel):
    run_date: str
    ranking: list[RankingEntry]
    top_tickers: list[str]            # Top 10
    worst_tickers: list[str]          # Bottom 10
    recommended_basket: list[BasketItem]
    basket_rationale: str
    sector_clusters: list[SectorCluster]
    competitive_relationships: list[str]
    supply_chain_links: list[str]
    scenario_signals: list[str]
    macro_themes: list[str]
    watchlist: list[str]
    systemic_risks: list[str]
    llm_commentary: str | None
    generated_at: str
```

### MacroAnalysis

```python
class MacroAnalysis(BaseModel):
    run_date: str
    macro_regime: str                 # "risk-on" | "risk-off" | "transitioning" | "uncertain"
    market_breadth: str               # "expanding" | "contracting" | "mixed"
    key_macro_themes: list[str]
    macro_risks: list[str]
    sector_rotation_signal: str
    yield_curve_interpretation: str
    dollar_impact: str
    macro_commentary: str             # Narrativa 3-5 paragrafi
    macro_score: float                # 0-100
    indicators: list[MacroIndicator]
    yield_curve_spread: float | None
    vix_level: float | None
    sector_performance: dict[str, float]
    generated_at: str
```

---

## 16. API REST

**File:** `src/api/app.py`
**Framework:** FastAPI con CORS abilitato (tutti gli origin)

### Endpoints

#### `GET /health`
```json
{"status": "ok"}
```

#### `GET /api/runs`
```json
{"runs": ["2026-03-15", "2026-03-16", "2026-03-17"]}
```

#### `GET /api/runs/latest`
```json
{
  "run_date": "2026-03-17",
  "weekly_summary": { /* WeeklySummary se disponibile */ }
}
```

#### `GET /api/tickers?run_date=YYYY-MM-DD`
Carica tutti i file `{SYMBOL}.json` dall'output della run più recente (o `run_date` specificato).
```json
{
  "run_date": "2026-03-17",
  "tickers": [/* lista TickerAnalysis */]
}
```

#### `GET /api/ticker/{symbol}?run_date=YYYY-MM-DD`
```json
{ /* TickerAnalysis completo */ }
```

#### `GET /api/weekly-summary/latest`
```json
{ /* WeeklySummary */ }
```

#### `GET /api/macro/latest?run_date=YYYY-MM-DD`
```json
{ /* MacroAnalysis */ }
```

#### `GET /api/live/quote/{symbol}?period=3mo`
Dati real-time via yfinance (no pipeline run, TTL cache 4h):
```json
{
  "symbol": "AAPL",
  "period": "3mo",
  "current_price": 185.20,
  "change_1d": 0.0142,
  "change_1m": 0.0312,
  "change_3m": -0.0823,
  "price_history": [{"date": "...", "open": ..., "close": ..., "volume": ...}]
}
```

#### `GET /api/live/news/{symbol}?limit=15`
News real-time via Yahoo Finance (no pipeline):
```json
{
  "symbol": "AAPL",
  "articles": [{"title": "...", "url": "...", "source": "...", "published_at": "...", "summary": "..."}]
}
```

#### `POST /api/run-analysis` — Avvia pipeline completa

**Request body:**
```json
{
  "run_date": "2026-03-17",
  "period": "3y",
  "symbols": ["AAPL", "MSFT"],
  "wait_for_batch": true,
  "force_refresh": false,
  "dry_run": false,
  "use_batch": false,
  "openai_news_research": false
}
```

**Response:**
```json
{"status": "completed", "result": { /* output completo FullPipeline.run_all() */ }}
```

#### `POST /api/run-single-ticker/{symbol}` — Pipeline per singolo ticker

Esegue market → metrics → news → ticker_analysis → weekly_summary per un solo simbolo.

---

## 17. Script CLI

**Directory:** `backend/scripts/`
**Nota:** tutti gli script usano `_bootstrap.py` per aggiungere `src/` al path Python.

### `run_all.py` — Pipeline completa

```bash
python scripts/run_all.py [OPTIONS]

--run-date YYYY-MM-DD      Data run (default: oggi)
--period 6mo|1y|3y|5y      Periodo storia (default: 3y)
--symbols AAPL,MSFT,...    Filtra ticker
--force-refresh            Ignora cache, scarica tutto
--no-wait-for-batch        Non attendere completamento batch OpenAI

# Modalità analisi:
--static                   Analisi statica (zero LLM, costo zero)
--live                     Abilita LLM (disabilita dry_run)
--live-no-batch            LLM diretto sincrono (senza batch queue)

# News:
--openai-news-research     Usa web search OpenAI per news
--openai-news-model MODEL  Sovrascrive modello news
--news-workers N           Worker paralleli per news research

# Skip stages:
--skip-news                Riusa news già salvate su disco
--skip-macro               Salta pipeline macro
--llm-only                 Salta market/metrics/news (solo analisi LLM su dati esistenti)
```

### `run_api.py` — Server FastAPI

```bash
python scripts/run_api.py [--host 0.0.0.0] [--port 8000] [--reload]
```

### Altri script (pipeline individuali)

```bash
python scripts/run_market_data.py --period 3y [--symbols AAPL,MSFT] [--force-refresh]
python scripts/run_metrics.py [--symbols AAPL]
python scripts/run_news_context.py [--symbols AAPL] [--openai-news-research]
python scripts/run_llm_ticker_analysis.py [--live] [--live-no-batch] [--symbols AAPL]
python scripts/run_weekly_summary.py
python scripts/run_single_ticker.py AAPL [--live] [--live-no-batch]
python scripts/run_macro.py
python scripts/sync_openai_batches.py   # Sincronizza batch pending dal registry
python scripts/export_schemas.py        # Esporta JSON Schema in config/schemas/
```

---

## 18. Dipendenze

**File:** `backend/requirements.txt`

| Pacchetto | Versione | Utilizzo |
|---|---|---|
| `fastapi` | ≥0.115.0 | Web framework API |
| `uvicorn` | ≥0.32.0 | ASGI server |
| `pydantic` | ≥2.9.0 | Validazione dati e schemi |
| `pydantic-settings` | ≥2.6.0 | Settings da env vars |
| `python-dotenv` | ≥1.0.1 | Carica file `.env` |
| `openai` | ≥1.52.0 | Client OpenAI SDK (usato anche per endpoint compatibili) |
| `yfinance` | ≥0.2.50 | Dati mercato e news da Yahoo Finance |
| `pandas` | ≥2.2.0 | Manipolazione dati OHLCV |
| `numpy` | ≥1.26.0 | Calcoli numerici (RSI, Sharpe, ecc.) |
| `requests` | ≥2.32.0 | HTTP client generico |
| `tenacity` | ≥9.0.0 | Retry decorator con backoff esponenziale |

**Dipendenze opzionali (dev):**
```bash
pip install -e ".[dev]"   # pytest, pytest-cov, ruff
```

---

## 19. Flusso dati end-to-end

```
INPUT: tickers.json → [AAPL, MSFT, NVDA, ...]

┌─────────────────────────────────────────────────────────┐
│ MarketDataPipeline                                      │
│   yfinance.download() → DataFrame OHLCV 3Y             │
│   yf.Ticker().info   → fundamentals dict               │
│   Cache TTL: 24h (history), 72h (fundamentals)         │
│   Output: raw/YYYY-MM-DD/market_data/*.csv              │
│            raw/YYYY-MM-DD/fundamentals/*.json           │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ MetricsPipeline                                         │
│   compute_quant_metrics() → RSI, Sharpe, beta, MA...   │
│   normalize_fundamentals() → Graham Number, MoS...     │
│   serialize_price_history() → list[PricePoint]         │
│   Output: processed/YYYY-MM-DD/metrics/*.json           │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ NewsPipeline                                            │
│   Yahoo Finance → company_news, sector_news            │
│   (opt) OpenAI web search → arricchisce con sentiment  │
│   (opt) Mock provider → fallback offline               │
│   Output: processed/YYYY-MM-DD/news/*.json             │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ TickerAnalysisPipeline                                  │
│                                                         │
│   StaticAnalysisEngine (analysis_mode=static):         │
│     Rule-based scores, MA levels, Graham metrics       │
│     Narrativa tecnica e fondamentale data-driven       │
│                                                         │
│   TickerLLMAnalysisEngine (analysis_mode=llm):         │
│     Direct: OpenAI/Groq/Ollama sincrono                │
│     Batch: OpenAI Batch API 24h (50% risparmio)        │
│     Fallback deterministico se LLM non disponibile     │
│                                                         │
│   Output: outputs/YYYY-MM-DD/{SYMBOL}.json             │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ WeeklySummaryPipeline                                   │
│   Composite score = 45%×benefit + 15%×sentiment        │
│                    + 20%×confidence - 30%×risk          │
│   Ranking + basket (max 2/settore, peso uguale)        │
│   Sector clusters, watchlist, systemic risks           │
│   (opt) LLM commentary su highlights compatti          │
│   Output: outputs/YYYY-MM-DD/weekly_summary.json        │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ MacroPipeline                                           │
│   ^VIX, ^TNX, ^IRX, ^GSPC, XLK, XLF, ...             │
│   Yield curve spread = 10Y - 3M                        │
│   Regime da VIX + breadth da settori                   │
│   (opt) LLM commentary macro                           │
│   Output: outputs/YYYY-MM-DD/macro_analysis.json        │
└────────────────────────┬────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ FastAPI (src/api/app.py)                                │
│   GET /api/tickers → lista TickerAnalysis              │
│   GET /api/weekly-summary/latest → WeeklySummary       │
│   GET /api/macro/latest → MacroAnalysis                │
│   GET /api/live/quote/{symbol} → prezzo real-time      │
│   POST /api/run-analysis → trigger pipeline            │
└─────────────────────────────────────────────────────────┘
                         ↓
              React Dashboard (webapp/)
```

---

*Documentazione generata per Market Score backend — versione corrente.*
