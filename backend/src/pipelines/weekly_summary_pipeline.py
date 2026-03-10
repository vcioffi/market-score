from __future__ import annotations

from src.config.settings import Settings
from src.llm.pipeline import WeeklyLLMEngine
from src.llm.schemas import TickerAnalysis
from src.portfolio.ranking import build_weekly_summary
from src.storage.json_store import JsonStorage
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class WeeklySummaryPipeline:
    def __init__(self, settings: Settings, storage: JsonStorage):
        self.settings = settings
        self.storage = storage
        self.weekly_llm = WeeklyLLMEngine(settings)

    def run(self, run_date: str, wait_for_batch: bool = True) -> dict:
        files = self.storage.list_ticker_output_files(run_date=run_date)
        analyses: list[TickerAnalysis] = []
        for file_path in files:
            try:
                analyses.append(TickerAnalysis.model_validate(self.storage.load_json(file_path)))
            except Exception as exc:
                LOGGER.warning("Skipping invalid ticker output %s: %s", file_path.name, exc)

        summary = build_weekly_summary(run_date=run_date, analyses=analyses)

        artifacts_dir = self.storage.processed_dir / run_date / "llm"
        commentary, llm_metadata = self.weekly_llm.generate_commentary(
            run_date=run_date,
            deterministic_summary=summary.model_dump(mode="json"),
            artifacts_dir=artifacts_dir,
            wait_for_batch=wait_for_batch,
        )
        if commentary:
            summary.llm_commentary = commentary

        self.storage.save_weekly_summary(run_date=run_date, payload=summary.model_dump(mode="json"))

        return {
            "run_date": run_date,
            "tickers": len(analyses),
            "has_llm_commentary": bool(commentary),
            "llm_metadata": llm_metadata,
        }
