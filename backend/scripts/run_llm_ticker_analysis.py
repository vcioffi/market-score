from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.pipelines.ticker_analysis_pipeline import TickerAnalysisPipeline
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.dates import today_iso
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM ticker analysis using OpenAI batch/direct mode or fallback")
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols")
    parser.add_argument(
        "--no-wait-for-batch",
        action="store_true",
        help="Do not wait for OpenAI batch completion; returns provisional fallback outputs",
    )
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode (OpenAI enabled)")
    parser.add_argument(
        "--live-no-batch",
        action="store_true",
        help="Disable dry-run and use synchronous OpenAI calls (no batch queue, immediate results)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.live_no_batch:
        settings.dry_run = False
        settings.openai_use_batch = False
        settings.openai_news_research_enabled = True
    else:
        settings.dry_run = not args.live

    configure_logging(settings.log_level)

    run_date = args.run_date or today_iso(settings.timezone)
    symbols = [item.strip().upper() for item in args.symbols.split(",")] if args.symbols else None
    wait_for_batch = not args.no_wait_for_batch

    storage = JsonStorage(settings.raw_data_dir, settings.processed_data_dir, settings.outputs_data_dir)
    repository = TickerRepository(settings.ticker_config_path)

    pipeline = TickerAnalysisPipeline(settings, storage, repository)
    result = pipeline.run(run_date=run_date, wait_for_batch=wait_for_batch, symbols=symbols)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
