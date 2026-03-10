from __future__ import annotations

from pydantic import BaseModel, Field


class TickerProfile(BaseModel):
    symbol: str = Field(min_length=1)
    company_name: str = ""
    sector: str = "Unknown"
    industry: str = "Unknown"
    market: str = "US"
    peers: list[str] = Field(default_factory=list)
