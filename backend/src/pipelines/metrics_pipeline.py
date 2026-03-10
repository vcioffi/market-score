from __future__ import annotations

from src.config.settings import Settings
from src.metrics.service import build_metrics_bundle
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class MetricsPipeline:
    def __init__(self, settings: Settings, storage: JsonStorage, repository: TickerRepository):
        self.settings = settings
        self.storage = storage
        self.repository = repository

    def run(self, run_date: str, symbols: list[str] | None = None) -> dict:
        profiles = self.repository.load_symbols(limit=self.settings.max_tickers_per_run)
        if symbols:
            target = {item.upper() for item in symbols}
            profiles = [item for item in profiles if item.symbol.upper() in target]

        benchmark_history = self.storage.load_history(run_date=run_date, symbol=self.settings.benchmark_symbol)

        processed = 0
        failed: list[str] = []

        for profile in profiles:
            try:
                history = self.storage.load_history(run_date=run_date, symbol=profile.symbol)
                fundamentals = self.storage.load_fundamentals(run_date=run_date, symbol=profile.symbol)
                metrics = build_metrics_bundle(
                    history=history,
                    benchmark_history=benchmark_history,
                    fundamentals_raw=fundamentals,
                    risk_free_rate_annual=self.settings.risk_free_rate_annual,
                )
                self.storage.save_processed_metrics(run_date=run_date, symbol=profile.symbol, payload=metrics)
                processed += 1
            except Exception as exc:
                LOGGER.error("Metrics pipeline failed for %s: %s", profile.symbol, exc)
                failed.append(profile.symbol)

        return {
            "run_date": run_date,
            "processed": processed,
            "failed": failed,
        }
