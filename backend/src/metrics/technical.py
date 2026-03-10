from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def _safe_float(value: float | int | np.floating | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return float(value)


def _return_for_days(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    start = close.iloc[-days - 1]
    end = close.iloc[-1]
    if start == 0:
        return None
    return _safe_float((end / start) - 1)


def compute_quant_metrics(history: pd.DataFrame, benchmark_history: pd.DataFrame, risk_free_rate_annual: float) -> dict:
    if history.empty:
        raise ValueError("History dataframe is empty")

    close = history["Close"].dropna()
    volume = history["Volume"].dropna()
    returns = close.pct_change().dropna()

    benchmark_close = benchmark_history["Close"].dropna()
    benchmark_returns = benchmark_close.pct_change().dropna()

    aligned = pd.concat([returns, benchmark_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "benchmark"]

    rolling_vol = returns.rolling(20).std() * sqrt(TRADING_DAYS_PER_YEAR)
    rolling_drawdown = close / close.cummax() - 1

    downside = returns[returns < 0]
    rf_daily = risk_free_rate_annual / TRADING_DAYS_PER_YEAR

    sharpe = None
    if returns.std() and returns.std() > 0:
        sharpe = ((returns.mean() - rf_daily) / returns.std()) * sqrt(TRADING_DAYS_PER_YEAR)

    sortino = None
    if downside.std() and downside.std() > 0:
        sortino = ((returns.mean() - rf_daily) / downside.std()) * sqrt(TRADING_DAYS_PER_YEAR)

    beta = None
    correlation = None
    if len(aligned) > 5:
        covariance = aligned["asset"].cov(aligned["benchmark"])
        benchmark_var = aligned["benchmark"].var()
        if benchmark_var and benchmark_var > 0:
            beta = covariance / benchmark_var
        correlation = aligned["asset"].corr(aligned["benchmark"])

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    ma_20 = close.rolling(20).mean()
    ma_50 = close.rolling(50).mean()
    ma_200 = close.rolling(200).mean()

    recent_window = 252 if len(close) > 252 else len(close)
    recent_slice = close.iloc[-recent_window:]
    recent_high = recent_slice.max()
    recent_low = recent_slice.min()
    latest_close = close.iloc[-1]

    distance_high = ((latest_close / recent_high) - 1) if recent_high else None
    distance_low = ((latest_close / recent_low) - 1) if recent_low else None

    avg_vol_20 = volume.tail(20).mean() if len(volume) >= 20 else volume.mean()
    latest_volume = volume.iloc[-1] if len(volume) else None
    vol_change = None
    if avg_vol_20 and avg_vol_20 > 0 and latest_volume is not None:
        vol_change = (latest_volume / avg_vol_20) - 1

    rolling_year_vol = returns.rolling(20).std() * sqrt(TRADING_DAYS_PER_YEAR)
    vol_threshold = rolling_year_vol.quantile(0.25) if len(rolling_year_vol.dropna()) > 20 else None
    latest_rolling_vol = rolling_year_vol.iloc[-1] if len(rolling_year_vol.dropna()) else None

    breakout_signal = bool(latest_close >= recent_high * 0.995) if recent_high else False
    volatility_compression = bool(
        latest_rolling_vol is not None and vol_threshold is not None and latest_rolling_vol <= vol_threshold
    )

    return {
        "returns": {
            "1m": _return_for_days(close, 21),
            "3m": _return_for_days(close, 63),
            "6m": _return_for_days(close, 126),
            "1y": _return_for_days(close, 252),
        },
        "rolling_volatility_20d": _safe_float(rolling_vol.iloc[-1] if len(rolling_vol.dropna()) else None),
        "max_drawdown": _safe_float(rolling_drawdown.min() if len(rolling_drawdown) else None),
        "sharpe_ratio": _safe_float(sharpe),
        "sortino_ratio": _safe_float(sortino),
        "beta": _safe_float(beta),
        "correlation_benchmark": _safe_float(correlation),
        "simple_momentum_3m": _return_for_days(close, 63),
        "rsi_14": _safe_float(rsi.iloc[-1] if len(rsi.dropna()) else None),
        "moving_averages": {
            "ma_20": _safe_float(ma_20.iloc[-1] if len(ma_20.dropna()) else None),
            "ma_50": _safe_float(ma_50.iloc[-1] if len(ma_50.dropna()) else None),
            "ma_200": _safe_float(ma_200.iloc[-1] if len(ma_200.dropna()) else None),
        },
        "distance_recent_high": _safe_float(distance_high),
        "distance_recent_low": _safe_float(distance_low),
        "average_volume_20d": _safe_float(avg_vol_20),
        "volume_change_vs_avg": _safe_float(vol_change),
        "signals": {
            "breakout": breakout_signal,
            "volatility_compression": volatility_compression,
        },
        "latest_close": _safe_float(latest_close),
    }


def serialize_price_history(history: pd.DataFrame, points: int = 180) -> list[dict]:
    data = history.tail(points).reset_index()
    date_col = "Date" if "Date" in data.columns else data.columns[0]
    payload: list[dict] = []
    for _, row in data.iterrows():
        payload.append(
            {
                "date": str(pd.to_datetime(row[date_col]).date()),
                "open": _safe_float(row.get("Open")),
                "high": _safe_float(row.get("High")),
                "low": _safe_float(row.get("Low")),
                "close": _safe_float(row.get("Close")),
                "volume": int(row.get("Volume", 0) or 0),
            }
        )
    return payload
