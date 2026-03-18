# Tutorial Operativo - Market Score

Questa guida ti porta da zero a una run reale, incluse prove veloci con 2 ticker.

## 1) Setup iniziale

**Linux / macOS:**
```bash
cd /path/to/market-score
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
cd "C:\path\to\market-score"
copy .env.example .env
```

### Backend

**Linux / macOS:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Webapp

**Linux / macOS / Windows:**
```bash
cd webapp
npm install
```

## 2) Configurazione LLM (scegli un provider)

Apri `.env` e configura il provider preferito:

### Opzione A — Analisi statica (zero costo, nessuna chiave)

Nessuna modifica necessaria. Usa il flag `--static` al momento dell'esecuzione.

### Opzione B — Ollama (locale, gratuito)

```bash
# Installa Ollama da https://ollama.com, poi:
ollama pull llama3.2
```

```env
MARKET_SCORE_DRY_RUN=false
MARKET_SCORE_LLM_BASE_URL=http://localhost:11434/v1
MARKET_SCORE_LLM_MODEL=llama3.2
MARKET_SCORE_LLM_USE_JSON_SCHEMA=false
```

### Opzione C — Groq (free tier, 14 400 req/giorno)

```env
MARKET_SCORE_DRY_RUN=false
MARKET_SCORE_LLM_BASE_URL=https://api.groq.com/openai/v1
MARKET_SCORE_LLM_API_KEY=gsk_...
MARKET_SCORE_LLM_MODEL=llama-3.1-8b-instant
```

### Opzione D — OpenAI (a pagamento)

```env
MARKET_SCORE_OPENAI_API_KEY=sk-...
MARKET_SCORE_DRY_RUN=false
MARKET_SCORE_OPENAI_USE_BATCH=true
MARKET_SCORE_OPENAI_COMPLETION_WINDOW=24h
```

Consigliato anche:

```env
MARKET_SCORE_OPENAI_TICKER_MAX_COMPLETION_TOKENS=1500
MARKET_SCORE_OPENAI_WEEKLY_MAX_COMPLETION_TOKENS=2000
```

## 3) Run completa (~60 ticker)

### Modalita statica (zero costo, nessuna chiave)

```bash
cd backend
python scripts/run_all.py --static
```

### Modalita live con OpenAI (batch, coda 24h)

```bash
python scripts/run_all.py --live
```

Nota:
- di default in `--live` il comando aspetta il completamento batch OpenAI;
- per output provvisori immediati (fallback + metadata batch):

```bash
python scripts/run_all.py --live --no-wait-for-batch
```

### Modalita live senza batch (risultati immediati)

```bash
python scripts/run_all.py --live-no-batch --symbols AAPL,MSFT
```

### Con ricerca web OpenAI per le news

```bash
python scripts/run_all.py --live-no-batch --openai-news-research --symbols NVDA,AMZN
```

### Con modello news specifico (es. deep-research)

```bash
python scripts/run_all.py --live-no-batch --openai-news-model o4-mini-deep-research --symbols NVDA,AMZN
```

Nota: `--openai-news-model` abilita automaticamente la ricerca news OpenAI. I modelli `deep-research` usano `search_context_size=medium` in modo automatico (requisito API).

Nel JSON finale controlla `news.provider_mode`, `news.openai_researched`, `news.openai_fallback` e `news.openai_errors` per verificare se OpenAI ha coperto tutti i ticker o c'e stato fallback.

## 4) Prova veloce con 2 ticker

### Opzione A: due ticker, analisi statica (nessun costo)

```bash
cd backend
python scripts/run_all.py --static --symbols AAPL,MSFT
```

### Opzione B: due ticker con LLM live (consigliata con OpenAI)

```bash
python scripts/run_all.py --live --symbols AAPL,MSFT
```

### Opzione C: via API backend

Avvia API:

```bash
python scripts/run_api.py --reload
```

Poi chiama endpoint:

```http
POST /api/run-analysis
{
  "dry_run": false,
  "wait_for_batch": true,
  "symbols": ["AAPL", "MSFT"]
}
```

## 5) Monitoraggio batch 24h (coda + download)

Dopo un comando con `--no-wait-for-batch`, i `batch_id` restano salvati nel registro locale.

```bash
cd backend
# Vedi cosa e ancora in coda
python scripts/sync_openai_batches.py --list-only

# Aggiorna stato remoto e scarica i batch completati
python scripts/sync_openai_batches.py

# Solo una data specifica
python scripts/sync_openai_batches.py --run-date 2026-03-07
```

Non serve lasciare il terminale aperto: puoi rilanciare questo comando quando vuoi. Se un batch e `completed` ma con richieste fallite, troverai `failure_messages` nel JSON di risposta.

## 6) Avvio API + Dashboard

### API

```bash
cd backend
python scripts/run_api.py --host 0.0.0.0 --port 8000 --reload
```

### Webapp

```bash
cd webapp
npm run dev
```

Apri `http://localhost:5173`.

## 7) Dove leggere gli output

I risultati vengono salvati in:

```text
backend/data/outputs/YYYY-MM-DD/
  <TICKER>.json
  weekly_summary.json
```

## 8) Comandi utili separati

```bash
python scripts/run_market_data.py --symbols AAPL,MSFT
python scripts/run_metrics.py --symbols AAPL,MSFT
python scripts/run_news_context.py --symbols AAPL,MSFT
python scripts/run_llm_ticker_analysis.py --live --symbols AAPL,MSFT
python scripts/run_weekly_summary.py
```

## 9) Run batch completa con deep-research (~60 ticker)

Workflow settimanale completo: deep-research per le news + Batch API per le analisi LLM.

### Step 1 — Lancia la pipeline

```bash
cd backend
python scripts/run_all.py --live --openai-news-model o4-mini-deep-research --news-workers 3 --no-wait-for-batch
```

- `--live` → Batch API OpenAI (costo -50%, finestra 24h)
- `--openai-news-model o4-mini-deep-research` → deep-research per le news (richiede verifica organizzazione)
- `--news-workers 3` → 3 ticker in parallelo per le news (~60 min su 100 ticker invece di ~3h)
- `--no-wait-for-batch` → ritorna subito, il batch LLM viene scaricato dopo

### Step 2 — Scarica i risultati LLM (~24h dopo)

```bash
python scripts/sync_openai_batches.py
```

### Varianti

News standard (no verifica organizzazione, piu veloce):
```bash
python scripts/run_all.py --live --openai-news-research --news-workers 5 --no-wait-for-batch
```

Tutto immediato senza batch (costo pieno, risultati subito):
```bash
python scripts/run_all.py --live-no-batch --openai-news-model o4-mini-deep-research --news-workers 3
```

### Tempi stimati (100 ticker)

| Modalita | News | Analisi LLM | Totale attesa |
|---|---|---|---|
| Batch + deep-research, 3 workers | ~60 min | ~24h (batch) | ~25h |
| Batch + news standard, 5 workers | ~20 min | ~24h (batch) | ~24h |
| No-batch + deep-research, 3 workers | ~60 min | ~30 min | ~1.5h |
| No-batch + news standard, 5 workers | ~20 min | ~30 min | ~50 min |

## 10) Troubleshooting rapido

- Nessuna chiave API disponibile: usa `--static` per analisi deterministica con dati reali e zero costo.
- Errore `openai package is required...`: installa requirements nel venv corretto.
- Se non hai ancora chiavi o rete: usa `dry_run=true` per fallback locale deterministico.
- **Linux/macOS** — attivazione venv: `source .venv/bin/activate`
- **Windows** — attivazione venv: `.\.venv\Scripts\Activate.ps1`
- Se la build web fallisce con `tsc not recognized`: esegui `npm install` nella cartella `webapp`.
- Ollama: imposta `MARKET_SCORE_LLM_USE_JSON_SCHEMA=false` (Ollama non supporta strict JSON schema).
- News research restituisce status `incomplete`: aumenta `MARKET_SCORE_OPENAI_NEWS_MAX_OUTPUT_TOKENS` in `.env` (default: 8000).
- Direct mode restituisce `No JSON object found` o risposta vuota: controlla che il modello supporti `json_schema`. Aumenta `MARKET_SCORE_OPENAI_TICKER_MAX_COMPLETION_TOKENS` (default: 1500).
- `deep-research` model con errore `search_context_size`: risolto automaticamente, usa sempre `medium`.
- News lente su molti ticker: aggiungi `--news-workers 5` (standard) o `--news-workers 3` (deep-research).
