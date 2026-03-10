from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.market_data.client import MarketDataClient
from src.pipelines.market_data_pipeline import MarketDataPipeline
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.dates import today_iso
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OHLCV and fundamentals for configured tickers")
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument("--period", type=str, default=None)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    run_date = args.run_date or today_iso(settings.timezone)
    symbols = [item.strip().upper() for item in args.symbols.split(",")] if args.symbols else None

    storage = JsonStorage(settings.raw_data_dir, settings.processed_data_dir, settings.outputs_data_dir)
    repository = TickerRepository(settings.ticker_config_path)
    client = MarketDataClient(settings.raw_data_dir)

    pipeline = MarketDataPipeline(settings, storage, repository, client)
    result = pipeline.run(
        run_date=run_date,
        period=args.period,
        force_refresh=args.force_refresh,
        symbols=symbols,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
