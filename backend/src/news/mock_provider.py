from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.news.models import NewsArticle
from src.news.provider_base import NewsProvider


class MockNewsProvider(NewsProvider):
    """Fallback provider used when online sources fail or API keys are missing."""

    def _build_article(self, symbol: str, title: str, category: str, source: str) -> NewsArticle:
        return NewsArticle(
            title=title,
            url=f"https://example.com/news/{symbol.lower()}-{abs(hash(title)) % 100000}",
            source=source,
            published_at=datetime.now(timezone.utc) - timedelta(hours=abs(hash(title)) % 72),
            summary=title,
            related_symbol=symbol,
            category=category,
        )

    def fetch_company_news(self, symbol: str) -> list[NewsArticle]:
        titles = [
            f"{symbol} reports updates that impact near-term execution",
            f"Analysts revise {symbol} expectations after management commentary",
            f"Institutional flows on {symbol} highlight momentum and volatility",
        ]
        return [self._build_article(symbol, title, "company", "MockWire") for title in titles]

    def fetch_sector_news(self, symbol: str, peers: list[str]) -> list[NewsArticle]:
        peer = peers[0] if peers else "sector peers"
        titles = [
            f"Sector pricing trends influence outlook for {symbol} and {peer}",
            f"Supply chain signals for {symbol} industry remain mixed",
            f"Macro rates and regulation remain key drivers for {symbol} sector",
        ]
        return [self._build_article(symbol, title, "sector", "MockWire") for title in titles]
