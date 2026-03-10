from __future__ import annotations

from abc import ABC, abstractmethod

from src.news.models import NewsArticle


class NewsProvider(ABC):
    """Interface for company and sector/scenario news providers."""

    @abstractmethod
    def fetch_company_news(self, symbol: str) -> list[NewsArticle]:
        raise NotImplementedError

    @abstractmethod
    def fetch_sector_news(self, symbol: str, peers: list[str]) -> list[NewsArticle]:
        raise NotImplementedError
