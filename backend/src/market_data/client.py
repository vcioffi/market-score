from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.utils.logging import get_logger
from src.utils.retry import with_retry

try:
    import yfinance as yf
except Exception:  # pragma: no cover - handled at runtime
    yf = None  # type: ignore

LOGGER = get_logger(__name__)


class MarketDataClient:
    """Fetch daily OHLCV and fundamental snapshots with local caching."""

    def __init__(self, raw_data_dir: Path):
        self.raw_data_dir = raw_data_dir
        self.cache_dir = raw_data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_yfinance(self) -> None:
        if yf is None:
            raise RuntimeError(
                "yfinance is required to fetch market data. Install dependencies with: pip install -r requirements.txt"
            )

    def _history_cache_paths(self, symbol: str, period: str, interval: str) -> tuple[Path, Path]:
        key = f"{symbol.upper()}_{period}_{interval}".replace("/", "_")
        return (
            self.cache_dir / f"{key}.csv",
            self.cache_dir / f"{key}.meta.json",
        )

    def _fundamentals_cache_paths(self, symbol: str) -> tuple[Path, Path]:
        key = f"{symbol.upper()}_fundamentals"
        return (
            self.cache_dir / f"{key}.json",
            self.cache_dir / f"{key}.meta.json",
        )

    def _cache_is_fresh(self, meta_file: Path, ttl_hours: int) -> bool:
        if not meta_file.exists():
            return False
        try:
            payload = json.loads(meta_file.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(payload["fetched_at"])
        except Exception:
            return False
        return fetched_at + timedelta(hours=ttl_hours) > datetime.now(timezone.utc)

    def _write_meta(self, meta_file: Path) -> None:
        meta_file.write_text(
            json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8",
        )

    @with_retry(attempts=3)
    def _download_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        self._ensure_yfinance()
        data = yf.download(
            tickers=symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if data.empty:
            raise ValueError(f"No market data returned for {symbol}")
        return data

    def fetch_history(
        self,
        symbol: str,
        period: str,
        interval: str = "1d",
        force_refresh: bool = False,
        cache_ttl_hours: int = 24,
    ) -> pd.DataFrame:
        csv_file, meta_file = self._history_cache_paths(symbol, period, interval)

        if not force_refresh and csv_file.exists() and self._cache_is_fresh(meta_file, cache_ttl_hours):
            LOGGER.debug("Using cached history for %s", symbol)
            return pd.read_csv(csv_file, parse_dates=["Date"]).set_index("Date")

        try:
            frame = self._download_history(symbol=symbol, period=period, interval=interval)
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = [col[0] for col in frame.columns]

            frame = frame.reset_index().rename(columns={"Datetime": "Date"}).set_index("Date")
            frame = frame[["Open", "High", "Low", "Close", "Volume"]]
            frame.to_csv(csv_file)
            self._write_meta(meta_file)
            return frame
        except Exception as exc:
            LOGGER.warning("Market data fetch failed for %s: %s", symbol, exc)
            if csv_file.exists():
                LOGGER.warning("Falling back to cached history for %s", symbol)
                return pd.read_csv(csv_file, parse_dates=["Date"]).set_index("Date")
            raise

    @with_retry(attempts=2)
    def _download_fundamentals(self, symbol: str) -> dict:
        self._ensure_yfinance()
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        return {
            "market_cap": info.get("marketCap"),
            "revenue_growth": info.get("revenueGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "earnings_growth": info.get("earningsGrowth"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            # Additional fundamental metrics for Graham-style analysis
            "return_on_equity": info.get("returnOnEquity"),
            "price_to_book": info.get("priceToBook"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "book_value": info.get("bookValue"),
            "trailing_eps": info.get("trailingEps"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "ebitda_margins": info.get("ebitdaMargins"),
        }

    def fetch_fundamentals(self, symbol: str, force_refresh: bool = False, cache_ttl_hours: int = 72) -> dict:
        json_file, meta_file = self._fundamentals_cache_paths(symbol)

        if not force_refresh and json_file.exists() and self._cache_is_fresh(meta_file, cache_ttl_hours):
            return json.loads(json_file.read_text(encoding="utf-8"))

        try:
            payload = self._download_fundamentals(symbol)
            json_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._write_meta(meta_file)
            return payload
        except Exception as exc:
            LOGGER.warning("Fundamentals fetch failed for %s: %s", symbol, exc)
            if json_file.exists():
                LOGGER.warning("Falling back to cached fundamentals for %s", symbol)
                return json.loads(json_file.read_text(encoding="utf-8"))
            return {}
