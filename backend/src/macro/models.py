from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class MacroIndicator(BaseModel):
    symbol: str
    name: str
    category: str  # "volatility" | "market" | "yields" | "bonds" | "currency" | "commodity" | "sector"
    current_value: float | None = None
    change_1d: float | None = None   # fractional % change (e.g. 0.012 = +1.2%)
    change_1m: float | None = None
    change_3m: float | None = None


class MacroContext(BaseModel):
    """Raw macro data collected from market sources, before LLM analysis."""

    run_date: str
    indicators: list[MacroIndicator] = Field(default_factory=list)
    yield_curve_spread: float | None = None   # 10Y - 3M yield in percentage points
    vix_level: float | None = None
    sector_performance: dict[str, float] = Field(default_factory=dict)  # sector ETF -> 1M return
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
