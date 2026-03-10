from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.pipelines.news_pipeline import NewsPipeline
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.dates import today_iso
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Build qualitative news context for each ticker")
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols")
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode")
    parser.add_argument(
        "--openai-research",
        action="store_true",
        help="Use OpenAI web search research for company/sector news context",
    )
    parser.add_argument(
        "--openai-news-model",
        type=str,
        default=None,
        help="Override model used for OpenAI news research (example: gpt-5, o4-mini-deep-research)",
    )
    args = parser.parse_args()

    settings = get_settings()
    settings.dry_run = not args.live
    if args.openai_research:
        settings.openai_news_research_enabled = True
    if args.openai_news_model:
        settings.openai_model_news = args.openai_news_model.strip()
        settings.openai_news_research_enabled = True

    configure_logging(settings.log_level)

    run_date = args.run_date or today_iso(settings.timezone)
    symbols = [item.strip().upper() for item in args.symbols.split(",")] if args.symbols else None

    storage = JsonStorage(settings.raw_data_dir, settings.processed_data_dir, settings.outputs_data_dir)
    repository = TickerRepository(settings.ticker_config_path)

    pipeline = NewsPipeline(settings, storage, repository)
    result = pipeline.run(run_date=run_date, symbols=symbols)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
