from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.news.mock_provider import MockNewsProvider
from src.news.models import NewsArticle, NewsContext
from src.news.provider_base import NewsProvider
from src.news.yahoo_provider import YahooFinanceNewsProvider
from src.tickers.models import TickerProfile
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


class NewsContextService:
    """Prepare clean, token-aware qualitative context for LLM payloads."""

    def __init__(self, allow_mock_news: bool = True):
        self.primary_provider: NewsProvider = YahooFinanceNewsProvider()
        self.fallback_provider: NewsProvider | None = MockNewsProvider() if allow_mock_news else None

    def _limit_window(self, articles: list[NewsArticle], window_days: int) -> list[NewsArticle]:
        threshold = datetime.now(timezone.utc) - timedelta(days=window_days)
        limited = [item for item in articles if item.published_at is None or item.published_at >= threshold]
        return limited

    def _truncate_summary(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].strip() + "..."

    def _sanitize(self, article: NewsArticle, max_chars: int) -> NewsArticle:
        payload = article.model_copy()
        payload.summary = self._truncate_summary(payload.summary.strip(), max_chars=max_chars)
        payload.title = payload.title.strip()
        return payload

    def _dedupe(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        seen: set[tuple[str, str]] = set()
        output: list[NewsArticle] = []
        for article in articles:
            key = (article.title.lower(), article.url)
            if key in seen:
                continue
            seen.add(key)
            output.append(article)
        return output

    def build_context(
        self,
        profile: TickerProfile,
        max_company_news: int,
        max_sector_news: int,
        window_days: int,
        summary_char_limit: int,
    ) -> NewsContext:
        sources: list[str] = []
        company_news = self.primary_provider.fetch_company_news(profile.symbol)
        sector_news = self.primary_provider.fetch_sector_news(profile.symbol, profile.peers)
        if company_news or sector_news:
            sources.append("yfinance")

        if not company_news and self.fallback_provider is not None:
            company_news = self.fallback_provider.fetch_company_news(profile.symbol)
            sources.append("mock")
        if not sector_news and self.fallback_provider is not None:
            sector_news = self.fallback_provider.fetch_sector_news(profile.symbol, profile.peers)
            if "mock" not in sources:
                sources.append("mock")

        company_news = self._limit_window(company_news, window_days)
        sector_news = self._limit_window(sector_news, window_days)

        company_news = [self._sanitize(item, summary_char_limit) for item in company_news]
        sector_news = [self._sanitize(item, summary_char_limit) for item in sector_news]

        company_news = self._dedupe(company_news)[:max_company_news]
        sector_news = self._dedupe(sector_news)[:max_sector_news]

        context = NewsContext(company_news=company_news, sector_news=sector_news, sources_used=sources)
        LOGGER.debug(
            "News context for %s -> %d company, %d sector",
            profile.symbol,
            len(context.company_news),
            len(context.sector_news),
        )
        return context
