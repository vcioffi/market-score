from __future__ import annotations

import pandas as pd

from src.metrics.fundamentals import normalize_fundamentals
from src.metrics.technical import compute_quant_metrics, serialize_price_history


def build_metrics_bundle(
    history: pd.DataFrame,
    benchmark_history: pd.DataFrame,
    fundamentals_raw: dict,
    risk_free_rate_annual: float,
) -> dict:
    quant = compute_quant_metrics(
        history=history,
        benchmark_history=benchmark_history,
        risk_free_rate_annual=risk_free_rate_annual,
    )
    fundamentals = normalize_fundamentals(fundamentals_raw)
    return {
        "quant": quant,
        "fundamentals": fundamentals,
        "price_history": serialize_price_history(history),
    }
