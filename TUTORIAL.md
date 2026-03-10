# Tutorial Operativo - Market Score

Questa guida ti porta da zero a una run reale, incluse prove veloci con 2 ticker.

## 1) Setup iniziale

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score"
copy .env.example .env
```

### Backend

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Webapp

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\webapp"
npm install
```

## 2) Configurazione API key OpenAI

Apri `.env` e imposta almeno:

```env
MARKET_SCORE_OPENAI_API_KEY=sk-...
MARKET_SCORE_DRY_RUN=false
MARKET_SCORE_OPENAI_USE_BATCH=true
MARKET_SCORE_OPENAI_COMPLETION_WINDOW=24h
```

Consigliato anche:

```env
MARKET_SCORE_OPENAI_TICKER_MAX_COMPLETION_TOKENS=2200
MARKET_SCORE_OPENAI_WEEKLY_MAX_COMPLETION_TOKENS=2600
```

## 3) Run completa (100 ticker)

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\backend"
python scripts\run_all.py --live
```

Nota:
- di default in `--live` il comando aspetta il completamento batch OpenAI;
- per output provvisori immediati (fallback + metadata batch):

```powershell
python scripts\run_all.py --live --no-wait-for-batch
```

- per risultato LLM immediato senza batch (costo standard, nessuna coda 24h):

```powershell
python scripts\run_all.py --live-no-batch --symbols AAPL,MSFT
```


- per run reale immediata completa (OpenAI su analisi + ricerca web/sentiment news):

```powershell
python scripts\run_all.py --live-no-batch --openai-news-research --symbols NVDA,AMZN
```

- per usare un modello news specifico (es. deep-research):

```powershell
python scripts\run_all.py --live-no-batch --openai-news-model o4-mini-deep-research --symbols NVDA,AMZN
```

Nota: `--openai-news-model` abilita automaticamente la ricerca news OpenAI. I modelli `deep-research` usano `search_context_size=medium` in modo automatico (requisito API).

Nel JSON finale controlla `news.provider_mode`, `news.openai_researched`, `news.openai_fallback` e `news.openai_errors` per verificare se OpenAI ha coperto tutti i ticker o c'e stato fallback.
## 4) Prova veloce con 2 ticker

### Opzione A: due ticker specifici (consigliata)

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\backend"
python scripts\run_all.py --live --symbols AAPL,MSFT
```

### Opzione B: via API backend

Avvia API:

```powershell
python scripts\run_api.py --reload
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

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\backend"
# Vedi cosa e ancora in coda
python scripts\sync_openai_batches.py --list-only

# Aggiorna stato remoto e scarica i batch completati
python scripts\sync_openai_batches.py

# Solo una data specifica
python scripts\sync_openai_batches.py --run-date 2026-03-07
```

Non serve lasciare il terminale aperto: puoi rilanciare questo comando quando vuoi. Se un batch e `completed` ma con richieste fallite, troverai `failure_messages` nel JSON di risposta.

## 6) Avvio API + Dashboard

### API

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\backend"
python scripts\run_api.py --host 0.0.0.0 --port 8000 --reload
```

### Webapp

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\webapp"
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

```powershell
python scripts\run_market_data.py --symbols AAPL,MSFT
python scripts\run_metrics.py --symbols AAPL,MSFT
python scripts\run_news_context.py --symbols AAPL,MSFT
python scripts\run_llm_ticker_analysis.py --live --symbols AAPL,MSFT
python scripts\run_weekly_summary.py
```

## 9) Run batch completa con deep-research (100 ticker)

Workflow settimanale completo: deep-research per le news + Batch API per le analisi LLM.

### Step 1 — Lancia la pipeline

```powershell
cd "C:\Users\alexq\Desktop\Portfolio\Market Score\backend"
python scripts\run_all.py --live --openai-news-model o4-mini-deep-research --news-workers 3 --no-wait-for-batch
```

- `--live` → Batch API OpenAI (costo -50%, finestra 24h)
- `--openai-news-model o4-mini-deep-research` → deep-research per le news (richiede verifica organizzazione)
- `--news-workers 3` → 3 ticker in parallelo per le news (~60 min su 100 ticker invece di ~3h)
- `--no-wait-for-batch` → ritorna subito, il batch LLM viene scaricato dopo

### Step 2 — Scarica i risultati LLM (~24h dopo)

```powershell
python scripts\sync_openai_batches.py
```

### Varianti

News standard (no verifica organizzazione, piu veloce):
```powershell
python scripts\run_all.py --live --openai-news-research --news-workers 5 --no-wait-for-batch
```

Tutto immediato senza batch (costo pieno, risultati subito):
```powershell
python scripts\run_all.py --live-no-batch --openai-news-model o4-mini-deep-research --news-workers 3
```

### Tempi stimati (100 ticker)

| Modalita | News | Analisi LLM | Totale attesa |
|---|---|---|---|
| Batch + deep-research, 3 workers | ~60 min | ~24h (batch) | ~25h |
| Batch + news standard, 5 workers | ~20 min | ~24h (batch) | ~24h |
| No-batch + deep-research, 3 workers | ~60 min | ~30 min | ~1.5h |
| No-batch + news standard, 5 workers | ~20 min | ~30 min | ~50 min |

## 10) Troubleshooting rapido

- Errore `openai package is required...`: installa requirements nel venv corretto.
- Se non hai ancora chiavi o rete: usa `dry_run=true` per fallback locale.
- Se la build web fallisce con `tsc not recognized`: esegui `npm install` nella cartella `webapp`.
- News research restituisce status `incomplete`: aumenta `MARKET_SCORE_OPENAI_NEWS_MAX_OUTPUT_TOKENS` in `.env` (default: 8000).
- Direct mode restituisce `No JSON object found` o risposta vuota: controlla che il modello supporti `json_schema`. Aumenta `MARKET_SCORE_OPENAI_TICKER_MAX_COMPLETION_TOKENS`.
- `deep-research` model con errore `search_context_size`: risolto automaticamente, usa sempre `medium`.
- News lente su 100 ticker: aggiungi `--news-workers 5` (standard) o `--news-workers 3` (deep-research).

