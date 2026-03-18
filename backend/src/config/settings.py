from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_prefix="MARKET_SCORE_",
        case_sensitive=False,
        extra="ignore",
    )

    timezone: str = "Europe/Rome"
    log_level: str = "INFO"

    dry_run: bool = True
    # Analysis mode:
    #   "llm"    — use configured LLM backend (OpenAI, Ollama, Groq, etc.)
    #   "static" — deterministic rule-based analysis; real market data + news,
    #              zero LLM calls (free and offline-friendly)
    analysis_mode: str = "llm"
    max_tickers_per_run: int = 100

    benchmark_symbol: str = "SPY"
    default_history_period: str = "3y"
    history_interval: str = "1d"
    risk_free_rate_annual: float = 0.02

    max_company_news: int = 3
    max_sector_news: int = 3
    news_window_days: int = 30
    news_summary_char_limit: int = 200

    # Generic LLM backend (OpenAI-compatible API)
    # Set llm_base_url to use a free/local provider:
    #   Ollama (local):  http://localhost:11434/v1
    #   Groq (free):     https://api.groq.com/openai/v1
    #   Gemini (free):   https://generativelanguage.googleapis.com/v1beta/openai
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None  # overrides openai_model_ticker/weekly when set
    # Set to false for providers that don't support strict JSON schema (e.g. Ollama)
    llm_use_json_schema: bool = True

    # Legacy OpenAI settings (kept for backward compatibility)
    openai_api_key: str | None = None
    openai_model_ticker: str = "gpt-4o-mini"
    openai_model_weekly: str = "gpt-4o-mini"
    openai_model_news: str = "gpt-4o-mini"
    openai_use_batch: bool = True
    openai_completion_window: str = "24h"
    openai_poll_interval_seconds: int = 30
    openai_max_wait_minutes: int = 180
    openai_ticker_max_completion_tokens: int = 3000
    openai_weekly_max_completion_tokens: int = 3000
    openai_news_max_output_tokens: int = 12000
    openai_news_search_context_size: str = "medium"
    openai_news_research_enabled: bool = False
    # Parallel workers for OpenAI news research (1 = sequential, 5-10 = parallel)
    # Use >1 only with OpenAI news research enabled; each worker consumes API rate limit.
    openai_news_workers: int = 1

    @property
    def effective_llm_api_key(self) -> str | None:
        """API key for the active LLM backend."""
        return self.llm_api_key or self.openai_api_key

    @property
    def effective_llm_base_url(self) -> str | None:
        """Base URL for the active LLM backend (None = OpenAI default)."""
        return self.llm_base_url

    @property
    def effective_llm_model_ticker(self) -> str:
        return self.llm_model or self.openai_model_ticker

    @property
    def effective_llm_model_weekly(self) -> str:
        return self.llm_model or self.openai_model_weekly

    @property
    def llm_live_mode(self) -> bool:
        """True when a real LLM backend is configured (not dry-run)."""
        return bool(self.llm_base_url or self.effective_llm_api_key)

    allow_mock_news: bool = True

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])

    @property
    def backend_root(self) -> Path:
        return self.project_root / "backend"

    @property
    def ticker_config_path(self) -> Path:
        return self.backend_root / "config" / "tickers.json"

    @property
    def raw_data_dir(self) -> Path:
        return self.backend_root / "data" / "raw"

    @property
    def processed_data_dir(self) -> Path:
        return self.backend_root / "data" / "processed"

    @property
    def outputs_data_dir(self) -> Path:
        return self.backend_root / "data" / "outputs"

    @property
    def schemas_dir(self) -> Path:
        return self.backend_root / "config" / "schemas"

    @property
    def openai_batch_registry_path(self) -> Path:
        return self.processed_data_dir / "openai_batches_registry.json"

    def ensure_directories(self) -> None:
        for path in (
            self.raw_data_dir,
            self.processed_data_dir,
            self.outputs_data_dir,
            self.schemas_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
