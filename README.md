# Market Score

Market Score e una piattaforma open source per ricerca finanziaria assistita da AI: analizza circa 100 ticker per run, calcola metriche quantitative, costruisce contesto news, genera analisi strutturate con OpenAI e visualizza ranking e score in una web app moderna.

Il repository e pensato per una pubblicazione pubblica su GitHub: il codice, gli schemi e la documentazione possono essere condivisi, mentre chiavi API, cache locali e output generati devono restare fuori dal versionamento.

## Focus del progetto

- Ricerca finanziaria ripetibile con pipeline chiara tra dati, metriche, news e sintesi LLM.
- Approccio open source: codice leggibile, configurazione esplicita e componenti separate tra backend e web app.
- Output strutturati in JSON per poter riusare i risultati in API, dashboard o workflow futuri.

## Sicurezza prima della pubblicazione

- Non committare mai `.env`: contiene segreti locali come `MARKET_SCORE_OPENAI_API_KEY`.
- Usa `.env.example` come template pubblico e mantieni la chiave reale solo in `.env` locale.
- Prima di fare `git add .`, verifica con `git status --ignored` che `.env`, `.claude`, `.venv`, `node_modules` e gli output generati risultino ignorati.

## Obiettivi coperti

- Universo iniziale di 100 ticker con metadati modificabili.
- Download OHLCV giornaliero + snapshot fondamentali via Yahoo Finance (`yfinance`) con cache locale.
- Calcolo metriche quant richieste: return multi-orizzonte, vol rolling, max drawdown, Sharpe, Sortino, beta, correlazione, momentum, RSI, medie mobili, distanza da high/low, metriche volume, breakout/compressione.
- Modulo news con provider primario (`yfinance`) + fallback mock plug-and-play.
- Pipeline LLM in piu passaggi con schema JSON stabile e validazione pydantic.
- Chiamate OpenAI in batch con `completion_window=24h` per sfruttare modalita non prioritaria.
- Output datato per run: `backend/data/outputs/YYYY-MM-DD/*.json` + `weekly_summary.json`.
- API FastAPI con endpoint richiesti.
- Web app React + Vite con dashboard ranking, filtri, ricerca ticker, dettaglio completo e grafico prezzo.

## Struttura progetto

```text
Market Score/
  backend/
    config/
      tickers.json
      pipeline_config.json
      schemas/
        ticker_analysis.schema.json
        weekly_summary.schema.json
    data/
      raw/
      processed/
      outputs/
    scripts/
      run_all.py
      run_market_data.py
      run_metrics.py
      run_news_context.py
      run_llm_ticker_analysis.py
      run_weekly_summary.py
      run_single_ticker.py
      run_api.py
      export_schemas.py
      sync_openai_batches.py
    src/
      api/
      config/
      llm/
      market_data/
      metrics/
      news/
      pipelines/
      portfolio/
      storage/
      tickers/
      utils/
    tests/
  webapp/
    src/
      components/
      pages/
      services/
      types/
  .env.example
  README.md
```

## Setup rapido

### 1) Backend

```bash
cd "Market Score/backend"
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Variabili ambiente

```bash
cd "Market Score"
copy .env.example .env
```

Config principali:

- `MARKET_SCORE_OPENAI_API_KEY`: chiave OpenAI.
- `MARKET_SCORE_DRY_RUN`: `true` usa fallback deterministico senza chiamate LLM remote.
- `MARKET_SCORE_OPENAI_USE_BATCH`: lasciare `true` per batch API.
- `MARKET_SCORE_OPENAI_COMPLETION_WINDOW`: default `24h`.
- `MARKET_SCORE_OPENAI_TICKER_MAX_COMPLETION_TOKENS` e `MARKET_SCORE_OPENAI_WEEKLY_MAX_COMPLETION_TOKENS`: controllo output token LLM.

### 3) Export schema JSON (gia incluso)

```bash
cd "Market Score/backend"
python scripts/export_schemas.py
```

## Esecuzione pipeline

### Run completa

```bash
cd "Market Score/backend"
python scripts/run_all.py
```

Modalita live con OpenAI:

```bash
python scripts/run_all.py --live
```

Modalita live immediata senza batch (nessuna coda 24h):

```bash
python scripts/run_all.py --live-no-batch --symbols AAPL,MSFT
```

Modalita live totale (senza batch) con ricerca web/sentiment OpenAI:

```bash
python scripts/run_all.py --live-no-batch --openai-news-research --symbols NVDA,AMZN
```

Per forzare un modello news specifico (es. deep-research):

```bash
python scripts/run_all.py --live-no-batch --openai-news-research --symbols NVDA,AMZN --openai-news-model o4-mini-deep-research
```

Nota: `--openai-news-model` abilita automaticamente la ricerca news via OpenAI. Non serve aggiungere `--openai-news-research` esplicitamente.

Questa modalita usa OpenAI in chiamata sincrona per analisi ticker/weekly e per il contesto news via tool di web search.


Note:

- `--live` disabilita il fallback locale (usa batch API).
- `--live-no-batch` usa OpenAI in chiamata sincrona (senza batch), quindi ricevi risultati LLM subito a costo standard.
- `--openai-news-research` delega a OpenAI la ricerca web e il sentiment su azienda/contesto, con fallback automatico al provider locale se OpenAI fallisce su uno o piu ticker.
- `--openai-news-model` permette di scegliere il modello per la sola ricerca news (es. `gpt-5`, `o4-mini-deep-research`). I modelli `deep-research` usano automaticamente `search_context_size=medium` (requisito API).
- nel JSON `news` controlla `provider_mode`, `openai_researched`, `openai_fallback` e `openai_errors` per capire quanto del run e stato realmente coperto da OpenAI.
- con OpenAI attivo, il modulo usa Batch API con finestra `24h`.
- default: il sistema aspetta il batch in live mode per avere output LLM finali.
- usa `--no-wait-for-batch` se vuoi output provvisori immediati con fallback + metadata batch.

### Modelli consigliati

| Uso | Modello | Note |
|-----|---------|------|
| Analisi ticker/weekly (batch/direct) | `gpt-4o-mini`, `gpt-4o` | Vedi `.env` `MARKET_SCORE_OPENAI_MODEL_TICKER` |
| News research (web search) | `gpt-4o-mini` | Valore predefinito |
| News research deep | `o4-mini-deep-research` | Solo `search_context_size=medium`, gestito automaticamente |

### Monitoraggio coda batch e download risultati

Ogni submit salva il `batch_id` nel registro locale: `backend/data/processed/openai_batches_registry.json`.

```bash
# Lista batch ancora da scaricare (coda)
python scripts/sync_openai_batches.py --list-only

# Controlla OpenAI e scarica i batch completati
python scripts/sync_openai_batches.py

# Filtra per data run
python scripts/sync_openai_batches.py --run-date 2026-03-07
```

Se un batch e `completed` ma contiene richieste fallite, il comando mostra `failure_messages` con il motivo (es. parametro non supportato).

### Step singoli

```bash
python scripts/run_market_data.py --period 3y
python scripts/run_metrics.py
python scripts/run_news_context.py
python scripts/run_llm_ticker_analysis.py --live
python scripts/run_weekly_summary.py
```

### Run ticker singolo

```bash
python scripts/run_single_ticker.py AAPL --live
```

## Output dati

Ogni run e salvata in una cartella datata:

```text
backend/data/outputs/YYYY-MM-DD/
  AAPL.json
  MSFT.json
  ...
  weekly_summary.json
```

Gli output vengono generati localmente in `backend/data/outputs/YYYY-MM-DD/` e non sono pensati per il repository pubblico.

## API backend

Avvio server:

```bash
cd "Market Score/backend"
python scripts/run_api.py --host 0.0.0.0 --port 8000 --reload
```

Endpoint disponibili:

- `GET /api/runs/latest`
- `GET /api/runs`
- `GET /api/tickers`
- `GET /api/ticker/{symbol}`
- `GET /api/weekly-summary/latest`
- `POST /api/run-analysis`
- `POST /api/run-single-ticker/{symbol}`

## Web app

```bash
cd "Market Score/webapp"
npm install
npm run dev
```

Di default la webapp usa `http://localhost:8000` come backend (`VITE_API_BASE_URL`).

Funzioni UI incluse:

- homepage con top ticker settimanali
- ranking completo con filtri settore
- best basket consigliato
- macro themes + watchlist
- ricerca ticker
- dettaglio ticker con score, sintesi quant/qual, trigger, advice, fonti
- grafico storico prezzo (Recharts)

## OpenAI Batch 24h

Implementazione in `backend/src/llm/batch.py` + `backend/src/llm/pipeline.py`.

Flusso:

1. costruzione file JSONL batch per analisi ticker;
2. upload file e creazione job batch con endpoint `/v1/chat/completions`;
3. `completion_window=24h` configurabile via env;
4. polling opzionale e parsing output JSON con validazione schema;
5. fallback locale automatico se job non disponibile o non completato.

Per i batch lanciati in modalita `--no-wait-for-batch`, esegui periodicamente:

```bash
python scripts/sync_openai_batches.py
```

Il comando aggiorna lo stato remoto, scarica output disponibili e rigenera `weekly_summary.json` per le run aggiornate.

## Come aggiungere nuovi ticker

- Modifica `backend/config/tickers.json`.
- Ogni entry supporta:
  - `symbol`
  - `company_name`
  - `sector`
  - `industry`
  - `market`
  - `peers`

## Come cambiare modello OpenAI

Aggiorna `.env`:

- `MARKET_SCORE_OPENAI_MODEL_TICKER`
- `MARKET_SCORE_OPENAI_MODEL_WEEKLY`

## Test

```bash
cd "Market Score/backend"
pytest -q
```

## Estensioni future gia abilitate dall architettura

- aumento universo ticker (oltre 100)
- nuovi provider market/news
- nuove metriche tecniche/fondamentali
- modelli LLM multipli
- scheduling batch settimanale
- ranking custom per profilo rischio

## Note operative

- In assenza di chiavi o con `dry_run=true`, il progetto resta completamente eseguibile in locale grazie al fallback deterministic.
- Il modulo news evita HTML grezzo e salva contesto normalizzato (titolo, fonte, timestamp, summary, url).
- Schema JSON finale e stabile e disponibile in `backend/config/schemas/`.

## Troubleshooting

### OpenAI news research: "No JSON object found in model output"

Il modello ha restituito risposta incompleta o vuota (status `incomplete`). Cause comuni:
- Token output insufficienti: aumenta `MARKET_SCORE_OPENAI_NEWS_MAX_OUTPUT_TOKENS` in `.env` (default: 4000).
- Il modello ha eseguito ricerche web ma non ha generato testo strutturato: questo e gestito dal fallback automatico al provider locale.

### deep-research: "Deep research models only support search_context_size 'medium'"

Risolto automaticamente: i modelli `*-deep-research` usano sempre `search_context_size=medium`.

### Direct mode: "No JSON object found in model output" / risposta vuota

Il modello ha restituito risposta vuota o troncata. L output LLM ora usa structured output (`json_schema`) invece di `json_object` per maggiore affidabilita. Se il problema persiste:
- Verifica che il modello configurato supporti structured output (`json_schema` strict mode).
- Aumenta `MARKET_SCORE_OPENAI_TICKER_MAX_COMPLETION_TOKENS` (default: 2200).





## Guida rapida

Per una guida step-by-step completa usa [TUTORIAL.md](./TUTORIAL.md).


