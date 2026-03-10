from __future__ import annotations

from datetime import datetime, timezone

from src.news.models import NewsArticle
from src.news.provider_base import NewsProvider
from src.utils.logging import get_logger

try:
    import yfinance as yf
except Exception:  # pragma: no cover - handled at runtime
    yf = None  # type: ignore

LOGGER = get_logger(__name__)


class YahooFinanceNewsProvider(NewsProvider):
    """Collect news metadata from yfinance ticker endpoints."""

    def _extract(self, symbol: str, category: str) -> list[NewsArticle]:
        if yf is None:
            return []

        items = []
        try:
            raw_items = yf.Ticker(symbol).news or []
        except Exception as exc:
            LOGGER.warning("Failed to fetch yfinance news for %s: %s", symbol, exc)
            return []

        for item in raw_items:
            title = item.get("title") or "Untitled"
            url = item.get("link") or item.get("canonicalUrl", {}).get("url") or ""
            if not url:
                continue
            published_ts = item.get("providerPublishTime")
            published = (
                datetime.fromtimestamp(published_ts, tz=timezone.utc)
                if isinstance(published_ts, (float, int))
                else None
            )
            summary = item.get("summary") or title
            source = item.get("publisher") or "Yahoo Finance"
            items.append(
                NewsArticle(
                    title=title,
                    url=url,
                    source=source,
                    published_at=published,
                    summary=summary,
                    related_symbol=symbol,
                    category=category,
                )
            )
        return items

    def fetch_company_news(self, symbol: str) -> list[NewsArticle]:
        return self._extract(symbol=symbol, category="company")

    def fetch_sector_news(self, symbol: str, peers: list[str]) -> list[NewsArticle]:
        peer_candidates = [peer for peer in peers if peer.upper() != symbol.upper()]
        if not peer_candidates:
            return []

        aggregate: list[NewsArticle] = []
        for peer_symbol in peer_candidates[:3]:
            aggregate.extend(self._extract(symbol=peer_symbol, category="sector"))
        return aggregate
