from __future__ import annotations

from copy import deepcopy
import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import RunAnalysisRequest, RunSingleTickerRequest
from src.config.settings import get_settings
from src.market_data.client import MarketDataClient
from src.pipelines.market_data_pipeline import MarketDataPipeline
from src.pipelines.metrics_pipeline import MetricsPipeline
from src.pipelines.news_pipeline import NewsPipeline
from src.pipelines.run_all_pipeline import FullPipeline
from src.pipelines.ticker_analysis_pipeline import TickerAnalysisPipeline
from src.pipelines.weekly_summary_pipeline import WeeklySummaryPipeline
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.dates import today_iso
from src.utils.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
LOGGER = get_logger(__name__)

app = FastAPI(title="Market Score API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_storage() -> JsonStorage:
    return JsonStorage(
        raw_dir=settings.raw_data_dir,
        processed_dir=settings.processed_data_dir,
        outputs_dir=settings.outputs_data_dir,
    )


def _build_repository() -> TickerRepository:
    return TickerRepository(settings.ticker_config_path)


def _safe_load_json(storage: JsonStorage, path) -> Optional[dict]:
    try:
        return storage.load_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        LOGGER.warning("Invalid JSON artifact at %s: %s", path, exc)
        return None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/runs")
def list_runs() -> dict:
    storage = _build_storage()
    runs = storage.list_run_dates()
    return {"runs": runs}


@app.get("/api/runs/latest")
def latest_run() -> dict:
    storage = _build_storage()
    run_date = storage.latest_run_date()
    if not run_date:
        raise HTTPException(status_code=404, detail="No runs available")

    response = {"run_date": run_date}
    summary_path = settings.outputs_data_dir / run_date / "weekly_summary.json"
    if summary_path.exists():
        summary = _safe_load_json(storage, summary_path)
        if summary is not None:
            response["weekly_summary"] = summary
    return response


@app.get("/api/tickers")
def list_tickers(run_date: Optional[str] = None) -> dict:
    storage = _build_storage()
    repository = _build_repository()

    selected_run = run_date or storage.latest_run_date()
    profiles = repository.load_symbols(limit=settings.max_tickers_per_run)

    score_map: dict[str, dict] = {}
    if selected_run:
        for file_path in storage.list_ticker_output_files(selected_run):
            payload = _safe_load_json(storage, file_path)
            if not payload:
                continue
            ticker = payload.get("ticker")
            if isinstance(ticker, str):
                score_map[ticker.upper()] = payload

    items = []
    for profile in profiles:
        output = score_map.get(profile.symbol.upper(), {})
        items.append(
            {
                **profile.model_dump(),
                "risk_score": output.get("risk_score"),
                "benefit_score": output.get("benefit_score"),
                "confidence_score": output.get("confidence_score"),
            }
        )

    return {"run_date": selected_run, "tickers": items}


@app.get("/api/ticker/{symbol}")
def ticker_detail(symbol: str, run_date: Optional[str] = None) -> dict:
    storage = _build_storage()
    selected_run = run_date or storage.latest_run_date()
    if not selected_run:
        raise HTTPException(status_code=404, detail="No run available")

    path = settings.outputs_data_dir / selected_run / f"{symbol.upper()}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Ticker {symbol.upper()} not found for run {selected_run}")

    payload = _safe_load_json(storage, path)
    if payload is None:
        raise HTTPException(status_code=500, detail=f"Ticker artifact {symbol.upper()} is invalid")
    return payload


@app.get("/api/weekly-summary/latest")
def latest_weekly_summary() -> dict:
    storage = _build_storage()
    run_date = storage.latest_run_date()
    if not run_date:
        raise HTTPException(status_code=404, detail="No run available")

    path = settings.outputs_data_dir / run_date / "weekly_summary.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Weekly summary missing")

    payload = _safe_load_json(storage, path)
    if payload is None:
        raise HTTPException(status_code=500, detail="Weekly summary artifact is invalid")
    return payload


@app.post("/api/run-analysis")
def run_analysis(payload: RunAnalysisRequest) -> dict:
    runtime_settings = deepcopy(settings)
    if payload.dry_run is not None:
        runtime_settings.dry_run = payload.dry_run
    if payload.use_batch is not None:
        runtime_settings.openai_use_batch = payload.use_batch
    if payload.openai_news_research is not None:
        runtime_settings.openai_news_research_enabled = payload.openai_news_research

    run_date = payload.run_date or today_iso(runtime_settings.timezone)
    pipeline = FullPipeline(runtime_settings)
    result = pipeline.run_all(
        run_date=run_date,
        period=payload.period,
        wait_for_batch=payload.wait_for_batch,
        force_refresh=payload.force_refresh,
        symbols=[item.upper() for item in payload.symbols] if payload.symbols else None,
    )
    return {"status": "completed", "result": result}


@app.post("/api/run-single-ticker/{symbol}")
def run_single_ticker(symbol: str, payload: RunSingleTickerRequest) -> dict:
    runtime_settings = deepcopy(settings)
    if payload.dry_run is not None:
        runtime_settings.dry_run = payload.dry_run
    if payload.use_batch is not None:
        runtime_settings.openai_use_batch = payload.use_batch
    if payload.openai_news_research is not None:
        runtime_settings.openai_news_research_enabled = payload.openai_news_research

    run_date = payload.run_date or today_iso(runtime_settings.timezone)

    storage = JsonStorage(
        raw_dir=runtime_settings.raw_data_dir,
        processed_dir=runtime_settings.processed_data_dir,
        outputs_dir=runtime_settings.outputs_data_dir,
    )
    repository = TickerRepository(runtime_settings.ticker_config_path)
    client = MarketDataClient(runtime_settings.raw_data_dir)

    market = MarketDataPipeline(runtime_settings, storage, repository, client)
    metrics = MetricsPipeline(runtime_settings, storage, repository)
    news = NewsPipeline(runtime_settings, storage, repository)
    ticker_analysis = TickerAnalysisPipeline(runtime_settings, storage, repository)
    weekly = WeeklySummaryPipeline(runtime_settings, storage)

    symbol = symbol.upper()
    market_result = market.run(
        run_date=run_date,
        period=payload.period,
        force_refresh=payload.force_refresh,
        symbols=[symbol],
    )
    metrics_result = metrics.run(run_date=run_date, symbols=[symbol])
    news_result = news.run(run_date=run_date, symbols=[symbol])
    analysis_result = ticker_analysis.run(
        run_date=run_date,
        wait_for_batch=payload.wait_for_batch,
        symbols=[symbol],
    )
    weekly_result = weekly.run(run_date=run_date, wait_for_batch=payload.wait_for_batch)

    return {
        "status": "completed",
        "run_date": run_date,
        "market_data": market_result,
        "metrics": metrics_result,
        "news": news_result,
        "ticker_analysis": analysis_result,
        "weekly_summary": weekly_result,
    }





