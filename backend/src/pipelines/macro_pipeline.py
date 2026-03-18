from __future__ import annotations

from src.config.settings import Settings
from src.llm.pipeline import MacroLLMEngine
from src.macro.service import MacroService
from src.storage.json_store import JsonStorage
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class MacroPipeline:
    """Collect macro indicators and generate LLM-powered macro analysis."""

    def __init__(self, settings: Settings, storage: JsonStorage):
        self.settings = settings
        self.storage = storage

    def run(self, run_date: str) -> dict:
        macro_service = MacroService(self.settings.raw_data_dir)

        LOGGER.info("Fetching macro indicators for run_date=%s", run_date)
        try:
            macro_context, fetch_errors = macro_service.fetch_macro_context(run_date=run_date)
        except Exception as exc:
            LOGGER.warning("MacroPipeline: failed to fetch macro context: %s", exc)
            return {"status": "error", "error": str(exc)}

        if fetch_errors:
            existing_errors = self.storage.load_pipeline_errors(run_date)
            self.storage.save_pipeline_errors(run_date, existing_errors + fetch_errors)

        context_dict = macro_context.model_dump()

        artifacts_dir = self.settings.processed_data_dir / run_date / "macro"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        LOGGER.info("Running macro LLM analysis")
        engine = MacroLLMEngine(self.settings)
        analysis, llm_meta = engine.generate_analysis(
            run_date=run_date,
            macro_context=context_dict,
            artifacts_dir=artifacts_dir,
        )

        self.storage.save_macro_analysis(run_date, analysis.model_dump())
        LOGGER.info(
            "MacroPipeline: saved macro_analysis.json — regime=%s, score=%.1f, llm_mode=%s",
            analysis.macro_regime,
            analysis.macro_score,
            llm_meta.get("mode"),
        )

        return {
            "status": "completed",
            "run_date": run_date,
            "macro_regime": analysis.macro_regime,
            "macro_score": analysis.macro_score,
            "indicators_count": len(analysis.indicators),
            "llm": llm_meta,
        }
