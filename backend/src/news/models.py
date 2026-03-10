from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    title: str
    url: str
    source: str = "unknown"
    published_at: datetime | None = None
    summary: str = ""
    related_symbol: str | None = None
    category: str = "company"


class SentimentSignal(BaseModel):
    score_0_100: float = Field(ge=0, le=100)
    label: str
    rationale: str = ""


class NewsContext(BaseModel):
    company_news: list[NewsArticle] = Field(default_factory=list)
    sector_news: list[NewsArticle] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
    company_sentiment: SentimentSignal | None = None
    sector_sentiment: SentimentSignal | None = None
