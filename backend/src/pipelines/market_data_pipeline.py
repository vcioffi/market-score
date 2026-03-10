from __future__ import annotations

from src.config.settings import Settings
from src.market_data.client import MarketDataClient
from src.market_data.mock_data import generate_mock_history
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class MarketDataPipeline:
    def __init__(
        self,
        settings: Settings,
        storage: JsonStorage,
        repository: TickerRepository,
        market_data_client: MarketDataClient,
    ):
        self.settings = settings
        self.storage = storage
        self.repository = repository
        self.market_data_client = market_data_client

    def run(
        self,
        run_date: str,
        period: str | None = None,
        force_refresh: bool = False,
        symbols: list[str] | None = None,
    ) -> dict:
        period = period or self.settings.default_history_period

        profiles = self.repository.load_symbols(limit=self.settings.max_tickers_per_run)
        if symbols:
            target = {item.upper() for item in symbols}
            profiles = [item for item in profiles if item.symbol.upper() in target]

        processed = 0
        failed: list[str] = []
        fallback_symbols: list[str] = []
        removed_symbols: list[str] = []

        benchmark = self.settings.benchmark_symbol
        try:
            benchmark_history = self.market_data_client.fetch_history(
                symbol=benchmark,
                period=period,
                interval=self.settings.history_interval,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            LOGGER.warning("Benchmark fetch failed (%s). Using mock benchmark data.", exc)
            benchmark_history = generate_mock_history(symbol=benchmark, period=period)
            fallback_symbols.append(benchmark)
        self.storage.save_history(run_date=run_date, symbol=benchmark, history=benchmark_history)

        for profile in profiles:
            try:
                history = self.market_data_client.fetch_history(
                    symbol=profile.symbol,
                    period=period,
                    interval=self.settings.history_interval,
                    force_refresh=force_refresh,
                )
                fundamentals = self.market_data_client.fetch_fundamentals(
                    symbol=profile.symbol,
                    force_refresh=force_refresh,
                )
            except ValueError as exc:
                # "No market data returned for X" → ticker likely delisted, remove permanently
                if "No market data returned for" in str(exc):
                    LOGGER.warning(
                        "Ticker %s appears delisted (no data from provider). "
                        "Removing from ticker universe.",
                        profile.symbol,
                    )
                    self.repository.remove_symbol(profile.symbol)
                    removed_symbols.append(profile.symbol)
                    continue
                # Other ValueError → transient, skip without removing
                LOGGER.warning("Skipping %s due to data error: %s", profile.symbol, exc)
                failed.append(profile.symbol)
                continue
            except Exception as exc:
                LOGGER.warning("Skipping %s due to unexpected error: %s", profile.symbol, exc)
                failed.append(profile.symbol)
                continue

            try:
                self.storage.save_history(run_date=run_date, symbol=profile.symbol, history=history)
                self.storage.save_fundamentals(run_date=run_date, symbol=profile.symbol, payload=fundamentals)
                processed += 1
            except Exception as exc:
                LOGGER.error("Market data pipeline save failed for %s: %s", profile.symbol, exc)
                failed.append(profile.symbol)

        return {
            "run_date": run_date,
            "processed": processed,
            "failed": failed,
            "fallback_symbols": sorted(set(fallback_symbols)),
            "removed_symbols": removed_symbols,
            "benchmark": benchmark,
            "period": period,
        }
