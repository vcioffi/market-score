from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics.technical import compute_quant_metrics


def _make_history(seed: int = 7) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range(end="2026-03-06", periods=320, freq="B")
    returns = np.random.normal(loc=0.0006, scale=0.02, size=len(dates))
    close = 100 * (1 + pd.Series(returns, index=dates)).cumprod()
    volume = np.random.randint(1_000_000, 4_000_000, size=len(dates))

    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.005,
            "Low": close * 0.99,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )


def test_compute_quant_metrics_returns_expected_keys() -> None:
    asset = _make_history(seed=11)
    benchmark = _make_history(seed=13)

    metrics = compute_quant_metrics(asset, benchmark, risk_free_rate_annual=0.02)

    assert "returns" in metrics
    assert "rolling_volatility_20d" in metrics
    assert "max_drawdown" in metrics
    assert "signals" in metrics
    assert set(metrics["returns"].keys()) == {"1m", "3m", "6m", "1y"}


def test_compute_quant_metrics_value_ranges() -> None:
    asset = _make_history(seed=2)
    benchmark = _make_history(seed=3)

    metrics = compute_quant_metrics(asset, benchmark, risk_free_rate_annual=0.02)

    assert metrics["rsi_14"] is None or 0 <= metrics["rsi_14"] <= 100
    assert metrics["correlation_benchmark"] is None or -1 <= metrics["correlation_benchmark"] <= 1
