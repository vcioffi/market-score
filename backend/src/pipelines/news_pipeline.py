from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config.settings import Settings
from src.news.models import NewsContext
from src.news.openai_research import OpenAINewsResearchService
from src.news.service import NewsContextService
from src.storage.json_store import JsonStorage
from src.tickers.models import TickerProfile
from src.tickers.repository import TickerRepository
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class NewsPipeline:
    def __init__(self, settings: Settings, storage: JsonStorage, repository: TickerRepository):
        self.settings = settings
        self.storage = storage
        self.repository = repository
        self.service = NewsContextService(allow_mock_news=self.settings.allow_mock_news)
        self.openai_service: OpenAINewsResearchService | None = None

        if self.settings.openai_news_research_enabled and not self.settings.dry_run and self.settings.openai_api_key:
            try:
                self.openai_service = OpenAINewsResearchService(
                    api_key=self.settings.openai_api_key,
                    model=self.settings.openai_model_news,
                    search_context_size=self.settings.openai_news_search_context_size,
                    max_output_tokens=self.settings.openai_news_max_output_tokens,
                )
            except Exception as exc:
                LOGGER.warning("OpenAI news research disabled due to initialization error: %s", exc)

    def _process_one(self, profile: TickerProfile, run_date: str) -> tuple[str, str | None, str | None]:
        """Fetch news for a single ticker. Returns (symbol, openai_status, error_msg).

        openai_status is 'ok' | 'fallback' | None (no openai attempted).
        """
        try:
            context: NewsContext | None = None
            openai_status: str | None = None

            if self.openai_service is not None:
                try:
                    context = self.openai_service.build_context(
                        profile=profile,
                        max_company_news=self.settings.max_company_news,
                        max_sector_news=self.settings.max_sector_news,
                        window_days=self.settings.news_window_days,
                        summary_char_limit=self.settings.news_summary_char_limit,
                    )
                    openai_status = "ok"
                except Exception as exc:
                    LOGGER.warning(
                        "OpenAI web research failed for %s, fallback to provider: %s",
                        profile.symbol, exc,
                    )
                    openai_status = str(exc)

            if context is None:
                context = self.service.build_context(
                    profile=profile,
                    max_company_news=self.settings.max_company_news,
                    max_sector_news=self.settings.max_sector_news,
                    window_days=self.settings.news_window_days,
                    summary_char_limit=self.settings.news_summary_char_limit,
                )

            self.storage.save_news_context(
                run_date=run_date,
                symbol=profile.symbol,
                payload=context.model_dump(mode="json"),
            )
            return profile.symbol, openai_status, None

        except Exception as exc:
            LOGGER.error("News pipeline failed for %s: %s", profile.symbol, exc)
            return profile.symbol, None, str(exc)

    def run(self, run_date: str, symbols: list[str] | None = None, max_workers: int = 1) -> dict:
        profiles = self.repository.load_symbols(limit=self.settings.max_tickers_per_run)
        if symbols:
            target = {item.upper() for item in symbols}
            profiles = [item for item in profiles if item.symbol.upper() in target]

        processed = 0
        failed: list[str] = []
        openai_researched: list[str] = []
        openai_fallback: list[str] = []
        openai_errors: dict[str, str] = {}

        # Use threads only when OpenAI research is active and workers > 1
        workers = max_workers if (self.openai_service is not None and max_workers > 1) else 1
        use_parallel = workers > 1

        if use_parallel:
            LOGGER.info(
                "News pipeline: running %d tickers with %d parallel workers",
                len(profiles), workers,
            )

        # Thread-safe accumulators
        _lock = threading.Lock()

        def _handle_result(symbol: str, openai_status: str | None, error: str | None) -> None:
            nonlocal processed
            with _lock:
                if error is not None:
                    failed.append(symbol)
                else:
                    processed += 1
                    if self.openai_service is not None:
                        if openai_status == "ok":
                            openai_researched.append(symbol)
                        else:
                            openai_fallback.append(symbol)
                            if openai_status:
                                openai_errors[symbol] = openai_status

        if use_parallel:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(self._process_one, profile, run_date): profile.symbol
                    for profile in profiles
                }
                for future in as_completed(futures):
                    symbol, openai_status, error = future.result()
                    _handle_result(symbol, openai_status, error)
        else:
            for profile in profiles:
                symbol, openai_status, error = self._process_one(profile, run_date)
                _handle_result(symbol, openai_status, error)

        openai_attempted = len(openai_researched) + len(openai_fallback)
        provider_mode = "provider_fallback"
        if self.openai_service is not None and openai_attempted > 0:
            if len(openai_researched) == openai_attempted:
                provider_mode = "openai_web_search"
            elif openai_researched:
                provider_mode = "mixed_openai_provider"

        return {
            "run_date": run_date,
            "processed": processed,
            "failed": failed,
            "provider_mode": provider_mode,
            "openai_researched": openai_researched,
            "openai_fallback": openai_fallback,
            "openai_errors": openai_errors,
        }
