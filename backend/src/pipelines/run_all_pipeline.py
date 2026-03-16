from __future__ import annotations

from src.config.settings import Settings
from src.market_data.client import MarketDataClient
from src.pipelines.macro_pipeline import MacroPipeline
from src.pipelines.market_data_pipeline import MarketDataPipeline
from src.pipelines.metrics_pipeline import MetricsPipeline
from src.pipelines.news_pipeline import NewsPipeline
from src.pipelines.ticker_analysis_pipeline import TickerAnalysisPipeline
from src.pipelines.weekly_summary_pipeline import WeeklySummaryPipeline
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class FullPipeline:
    """End-to-end weekly workflow for market scoring and portfolio summary."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = JsonStorage(
            raw_dir=settings.raw_data_dir,
            processed_dir=settings.processed_data_dir,
            outputs_dir=settings.outputs_data_dir,
        )
        self.repository = TickerRepository(settings.ticker_config_path)
        self.market_client = MarketDataClient(settings.raw_data_dir)

    def run_all(
        self,
        run_date: str,
        wait_for_batch: bool = False,
        period: str | None = None,
        force_refresh: bool = False,
        symbols: list[str] | None = None,
        skip_news: bool = False,
        skip_market: bool = False,
        skip_macro: bool = False,
    ) -> dict:
        market_pipeline = MarketDataPipeline(
            settings=self.settings,
            storage=self.storage,
            repository=self.repository,
            market_data_client=self.market_client,
        )
        metrics_pipeline = MetricsPipeline(
            settings=self.settings,
            storage=self.storage,
            repository=self.repository,
        )
        news_pipeline = NewsPipeline(
            settings=self.settings,
            storage=self.storage,
            repository=self.repository,
        )
        llm_pipeline = TickerAnalysisPipeline(
            settings=self.settings,
            storage=self.storage,
            repository=self.repository,
        )
        weekly_pipeline = WeeklySummaryPipeline(settings=self.settings, storage=self.storage)

        if skip_market:
            LOGGER.info("Skipping market data and metrics pipelines (--llm-only)")
            market_result = {"skipped": True}
            metrics_result = {"skipped": True}
        else:
            market_result = market_pipeline.run(
                run_date=run_date,
                period=period,
                force_refresh=force_refresh,
                symbols=symbols,
            )
            metrics_result = metrics_pipeline.run(run_date=run_date, symbols=symbols)

        if skip_news:
            LOGGER.info("Skipping news pipeline (reusing saved news context from disk)")
            news_result = {"skipped": True}
        else:
            news_result = news_pipeline.run(
                run_date=run_date,
                symbols=symbols,
                max_workers=self.settings.openai_news_workers,
            )

        llm_result = llm_pipeline.run(run_date=run_date, wait_for_batch=wait_for_batch, symbols=symbols)
        weekly_result = weekly_pipeline.run(run_date=run_date, wait_for_batch=wait_for_batch)

        if skip_macro:
            LOGGER.info("Skipping macro pipeline (--skip-macro)")
            macro_result: dict = {"skipped": True}
        else:
            macro_pipeline = MacroPipeline(settings=self.settings, storage=self.storage)
            macro_result = macro_pipeline.run(run_date=run_date)

        return {
            "run_date": run_date,
            "symbols": symbols,
            "market_data": market_result,
            "metrics": metrics_result,
            "news": news_result,
            "ticker_analysis": llm_result,
            "weekly_summary": weekly_result,
            "macro": macro_result,
        }
