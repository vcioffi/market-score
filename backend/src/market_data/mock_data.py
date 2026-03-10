from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def _period_to_points(period: str) -> int:
    normalized = period.lower().strip()
    mapping = {
        "6mo": 126,
        "1y": 252,
        "3y": 756,
        "5y": 1260,
    }
    return mapping.get(normalized, 756)


def generate_mock_history(symbol: str, period: str) -> pd.DataFrame:
    """Generate synthetic OHLCV when external data providers are unavailable."""

    points = _period_to_points(period)
    seed = abs(hash(symbol.upper())) % (2**32)
    rng = np.random.default_rng(seed)

    dates = pd.date_range(end=datetime.utcnow().date(), periods=points, freq="B")
    n = len(dates)  # actual number of business days (may differ from points near weekends)

    drift = 0.00025 + (seed % 100) / 100000
    volatility = 0.012 + ((seed // 100) % 60) / 10000

    daily_returns = rng.normal(loc=drift, scale=volatility, size=n)
    start_price = 40 + (seed % 250)
    close = start_price * np.cumprod(1 + daily_returns)

    high = close * (1 + np.abs(rng.normal(0.004, 0.003, size=n)))
    low = close * (1 - np.abs(rng.normal(0.004, 0.003, size=n)))
    open_ = close * (1 + rng.normal(0, 0.0025, size=n))
    volume = rng.integers(900_000, 8_000_000, size=n)

    frame = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )
    frame.index.name = "Date"
    return frame
