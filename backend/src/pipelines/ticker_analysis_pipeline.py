from __future__ import annotations

from src.config.settings import Settings
from src.llm.pipeline import TickerLLMAnalysisEngine, TickerLLMInput
from src.llm.static_engine import StaticAnalysisEngine
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class TickerAnalysisPipeline:
    def __init__(self, settings: Settings, storage: JsonStorage, repository: TickerRepository):
        self.settings = settings
        self.storage = storage
        self.repository = repository
        if settings.analysis_mode == "static":
            LOGGER.info("Using static analysis engine (no LLM)")
            self.engine: TickerLLMAnalysisEngine | StaticAnalysisEngine = StaticAnalysisEngine()
        else:
            self.engine = TickerLLMAnalysisEngine(settings)

    def run(self, run_date: str, wait_for_batch: bool = False, symbols: list[str] | None = None) -> dict:
        profiles = self.repository.load_symbols(limit=self.settings.max_tickers_per_run)
        if symbols:
            target = {item.upper() for item in symbols}
            profiles = [item for item in profiles if item.symbol.upper() in target]

        inputs: list[TickerLLMInput] = []
        for profile in profiles:
            try:
                metrics_payload = self.storage.load_processed_metrics(run_date=run_date, symbol=profile.symbol)
                news_payload = self.storage.load_news_context(run_date=run_date, symbol=profile.symbol)
                inputs.append(
                    TickerLLMInput(
                        profile=profile,
                        metrics_payload=metrics_payload,
                        news_payload=news_payload,
                    )
                )
            except Exception as exc:
                LOGGER.warning("Skipping %s due to missing artifacts: %s", profile.symbol, exc)

        artifacts_dir = self.storage.processed_dir / run_date / "llm"

        # Save each ticker to disk immediately after LLM parse — progress survives Ctrl+C
        already_saved: set[str] = set()

        def _save_immediately(symbol: str, model) -> None:
            self.storage.save_ticker_output(
                run_date=run_date,
                symbol=symbol,
                payload=model.model_dump(mode="json"),
            )
            already_saved.add(symbol.upper())
            LOGGER.debug("Saved ticker output: %s", symbol)

        analyses, metadata = self.engine.run(
            inputs=inputs,
            run_date=run_date,
            artifacts_dir=artifacts_dir,
            wait_for_batch=wait_for_batch,
            on_ticker_done=_save_immediately,
        )

        # Flush any remaining (fallback/batch results not covered by callback)
        for symbol, model in analyses.items():
            if symbol.upper() not in already_saved:
                self.storage.save_ticker_output(
                    run_date=run_date,
                    symbol=symbol,
                    payload=model.model_dump(mode="json"),
                )

        self.storage.save_json(artifacts_dir / "metadata.json", metadata)

        return {
            "run_date": run_date,
            "processed": len(analyses),
            "metadata": metadata,
        }
