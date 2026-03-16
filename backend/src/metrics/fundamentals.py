from __future__ import annotations

import math
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


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _graham_number(eps: float | None, book_value_per_share: float | None) -> float | None:
    """Benjamin Graham's intrinsic value formula: sqrt(22.5 * EPS * BVPS).

    Only valid when both EPS and BVPS are positive (profitable company with positive book value).
    """
    if eps is None or book_value_per_share is None:
        return None
    if eps <= 0 or book_value_per_share <= 0:
        return None
    try:
        return round(math.sqrt(22.5 * eps * book_value_per_share), 2)
    except (ValueError, ZeroDivisionError):
        return None


def normalize_fundamentals(raw: dict, current_price: float | None = None) -> dict:
    eps = _safe_float(raw.get("trailing_eps"))
    book_value = _safe_float(raw.get("book_value"))
    graham_num = _graham_number(eps, book_value)

    margin_of_safety: float | None = None
    if graham_num is not None and current_price and current_price > 0:
        margin_of_safety = round((graham_num - current_price) / graham_num * 100, 2)

    return {
        # Existing fields
        "revenue_growth": _normalize_ratio(raw.get("revenue_growth")),
        "debt_to_equity": raw.get("debt_to_equity"),
        "gross_margin": _normalize_ratio(raw.get("gross_margins")),
        "operating_margin": _normalize_ratio(raw.get("operating_margins")),
        "ebitda_margin": _normalize_ratio(raw.get("ebitda_margins")),
        "eps_growth": _normalize_ratio(raw.get("earnings_growth")),
        "pe": raw.get("trailing_pe"),
        "forward_pe": raw.get("forward_pe"),
        "free_cashflow": raw.get("free_cashflow"),
        "operating_cashflow": raw.get("operating_cashflow"),
        "market_cap": raw.get("market_cap"),
        # New Graham-style fundamental metrics
        "roe": _normalize_ratio(raw.get("return_on_equity")),
        "pb_ratio": _safe_float(raw.get("price_to_book")),
        "current_ratio": _safe_float(raw.get("current_ratio")),
        "quick_ratio": _safe_float(raw.get("quick_ratio")),
        "book_value_per_share": book_value,
        "trailing_eps": eps,
        "dividend_yield": _normalize_ratio(raw.get("dividend_yield")),
        "payout_ratio": _normalize_ratio(raw.get("payout_ratio")),
        # Computed Graham metrics
        "graham_number": graham_num,
        "margin_of_safety": margin_of_safety,
    }
