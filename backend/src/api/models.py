from __future__ import annotations

from pydantic import BaseModel


class RunAnalysisRequest(BaseModel):
    run_date: str | None = None
    period: str | None = None
    symbols: list[str] | None = None
    wait_for_batch: bool = True
    force_refresh: bool = False
    dry_run: bool | None = None
    use_batch: bool | None = None
    openai_news_research: bool | None = None


class RunSingleTickerRequest(BaseModel):
    run_date: str | None = None
    period: str | None = None
    wait_for_batch: bool = True
    force_refresh: bool = False
    dry_run: bool | None = None
    use_batch: bool | None = None
    openai_news_research: bool | None = None


class RunMacroRequest(BaseModel):
    run_date: str | None = None
