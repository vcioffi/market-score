from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.market_data.client import MarketDataClient
from src.pipelines.market_data_pipeline import MarketDataPipeline
from src.pipelines.metrics_pipeline import MetricsPipeline
from src.pipelines.news_pipeline import NewsPipeline
from src.pipelines.ticker_analysis_pipeline import TickerAnalysisPipeline
from src.pipelines.weekly_summary_pipeline import WeeklySummaryPipeline
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.dates import today_iso
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full flow for a single ticker")
    parser.add_argument("symbol", type=str)
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument("--period", type=str, default=None)
    parser.add_argument(
        "--no-wait-for-batch",
        action="store_true",
        help="Do not wait for OpenAI batch completion; returns provisional fallback outputs",
    )
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--openai-news-research", action="store_true", help="Use OpenAI web search research for news context")
    parser.add_argument(
        "--openai-news-model",
        type=str,
        default=None,
        help="Override model used for OpenAI news research (example: gpt-5, o4-mini-deep-research)",
    )
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode (OpenAI enabled)")
    parser.add_argument(
        "--live-no-batch",
        action="store_true",
        help="Disable dry-run and use synchronous OpenAI calls (no batch queue, immediate results)",
    )
    parser.add_argument(
        "--skip-weekly",
        action="store_true",
        help="Skip weekly summary generation for faster single-ticker test runs",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.live_no_batch:
        settings.dry_run = False
        settings.openai_use_batch = False
        settings.openai_news_research_enabled = True
    else:
        settings.dry_run = not args.live

    if args.openai_news_research:
        settings.openai_news_research_enabled = True
    if args.openai_news_model:
        settings.openai_model_news = args.openai_news_model.strip()
        settings.openai_news_research_enabled = True

    configure_logging(settings.log_level)

    run_date = args.run_date or today_iso(settings.timezone)
    symbol = args.symbol.upper()
    wait_for_batch = not args.no_wait_for_batch

    storage = JsonStorage(settings.raw_data_dir, settings.processed_data_dir, settings.outputs_data_dir)
    repository = TickerRepository(settings.ticker_config_path)
    client = MarketDataClient(settings.raw_data_dir)

    market = MarketDataPipeline(settings, storage, repository, client)
    metrics = MetricsPipeline(settings, storage, repository)
    news = NewsPipeline(settings, storage, repository)
    llm = TickerAnalysisPipeline(settings, storage, repository)

    result = {
        "market_data": market.run(
            run_date=run_date,
            period=args.period,
            force_refresh=args.force_refresh,
            symbols=[symbol],
        ),
        "metrics": metrics.run(run_date=run_date, symbols=[symbol]),
        "news": news.run(run_date=run_date, symbols=[symbol]),
        "ticker_analysis": llm.run(run_date=run_date, wait_for_batch=wait_for_batch, symbols=[symbol]),
    }

    if args.skip_weekly:
        result["weekly_summary"] = {
            "run_date": run_date,
            "tickers": 0,
            "has_llm_commentary": False,
            "llm_metadata": {"mode": "skipped", "reason": "skip_weekly_flag"},
        }
    else:
        weekly = WeeklySummaryPipeline(settings, storage)
        result["weekly_summary"] = weekly.run(run_date=run_date, wait_for_batch=wait_for_batch)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
