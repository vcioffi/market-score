from __future__ import annotations

from typing import Any


def _normalize_ratio(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if abs(result) > 50:
        return result / 100
    return result


def normalize_fundamentals(raw: dict) -> dict:
    return {
        "revenue_growth": _normalize_ratio(raw.get("revenue_growth")),
        "debt_to_equity": raw.get("debt_to_equity"),
        "gross_margin": _normalize_ratio(raw.get("gross_margins")),
        "operating_margin": _normalize_ratio(raw.get("operating_margins")),
        "eps_growth": _normalize_ratio(raw.get("earnings_growth")),
        "pe": raw.get("trailing_pe"),
        "forward_pe": raw.get("forward_pe"),
        "free_cashflow": raw.get("free_cashflow"),
        "operating_cashflow": raw.get("operating_cashflow"),
        "market_cap": raw.get("market_cap"),
    }
