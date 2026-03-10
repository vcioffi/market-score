from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.config.settings import Settings
from src.news.models import NewsArticle, NewsContext
from src.pipelines.news_pipeline import NewsPipeline
from src.storage.json_store import JsonStorage
from src.tickers.repository import TickerRepository


class _DummyOpenAIService:
    def __init__(self, *args, **kwargs):
        pass

    def build_context(
        self,
        profile,
        max_company_news: int,
        max_sector_news: int,
        window_days: int,
        summary_char_limit: int,
    ) -> NewsContext:
        if profile.symbol == "AAA":
            article = NewsArticle(
                title="AAA catalyst",
                url="https://example.com/aaa",
                source="example",
                published_at=datetime.now(timezone.utc),
                summary="Positive update",
                related_symbol="AAA",
                category="company",
            )
            return NewsContext(company_news=[article], sector_news=[], sources_used=["openai_web_search"])
        raise RuntimeError("forced openai failure")


class _DummyProviderService:
    def build_context(
        self,
        profile,
        max_company_news: int,
        max_sector_news: int,
        window_days: int,
        summary_char_limit: int,
    ) -> NewsContext:
        article = NewsArticle(
            title=f"{profile.symbol} provider news",
            url=f"https://provider.local/{profile.symbol.lower()}",
            source="provider",
            published_at=datetime.now(timezone.utc),
            summary="Provider fallback",
            related_symbol=profile.symbol,
            category="company",
        )
        return NewsContext(company_news=[article], sector_news=[], sources_used=["provider"])


def _make_settings(root: Path) -> Settings:
    backend = root / "backend"
    config_dir = backend / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    tickers = [
        {"symbol": "AAA", "company_name": "AAA Inc.", "sector": "Tech", "industry": "Software", "peers": ["BBB"]},
        {"symbol": "BBB", "company_name": "BBB Inc.", "sector": "Tech", "industry": "Hardware", "peers": ["AAA"]},
    ]
    (config_dir / "tickers.json").write_text(json.dumps(tickers), encoding="utf-8")

    settings = Settings(
        _env_file=None,
        project_root=root,
        dry_run=False,
        openai_api_key="test-key",
        openai_news_research_enabled=True,
        allow_mock_news=True,
    )
    settings.ensure_directories()
    return settings


def test_news_pipeline_reports_mixed_mode_when_openai_partially_fails(monkeypatch) -> None:
    monkeypatch.setattr("src.pipelines.news_pipeline.OpenAINewsResearchService", _DummyOpenAIService)

    root = Path("tests/.tmp_news_pipeline")
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)

    try:
        settings = _make_settings(root)
        storage = JsonStorage(settings.raw_data_dir, settings.processed_data_dir, settings.outputs_data_dir)
        repository = TickerRepository(settings.ticker_config_path)
        pipeline = NewsPipeline(settings=settings, storage=storage, repository=repository)
        pipeline.service = _DummyProviderService()

        result = pipeline.run(run_date="2026-03-08")

        assert result["processed"] == 2
        assert result["failed"] == []
        assert result["provider_mode"] == "mixed_openai_provider"
        assert result["openai_researched"] == ["AAA"]
        assert result["openai_fallback"] == ["BBB"]
        assert "BBB" in result["openai_errors"]
    finally:
        shutil.rmtree(root, ignore_errors=True)
