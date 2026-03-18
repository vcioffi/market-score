from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.macro.models import MacroContext, MacroIndicator
from src.utils.logging import get_logger

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None  # type: ignore

LOGGER = get_logger(__name__)

# Macro indicators to fetch via yfinance
_INDICATORS: list[dict] = [
    {"symbol": "^VIX",     "name": "CBOE VIX",            "category": "volatility"},
    {"symbol": "^GSPC",    "name": "S&P 500",             "category": "market"},
    {"symbol": "^IXIC",    "name": "NASDAQ Composite",    "category": "market"},
    {"symbol": "^RUT",     "name": "Russell 2000",        "category": "market"},
    {"symbol": "^TNX",     "name": "10Y Treasury Yield",  "category": "yields"},
    {"symbol": "^IRX",     "name": "3M T-Bill Yield",     "category": "yields"},
    {"symbol": "TLT",      "name": "20Y+ Treasury ETF",   "category": "bonds"},
    {"symbol": "HYG",      "name": "High Yield Bond ETF", "category": "bonds"},
    {"symbol": "DX-Y.NYB", "name": "US Dollar Index",     "category": "currency"},
    {"symbol": "GC=F",     "name": "Gold Futures",        "category": "commodity"},
    {"symbol": "CL=F",     "name": "Crude Oil Futures",   "category": "commodity"},
]

_SECTOR_ETFS: list[dict] = [
    {"symbol": "XLK",  "name": "Technology"},
    {"symbol": "XLF",  "name": "Financials"},
    {"symbol": "XLE",  "name": "Energy"},
    {"symbol": "XLV",  "name": "Health Care"},
    {"symbol": "XLI",  "name": "Industrials"},
    {"symbol": "XLY",  "name": "Consumer Discret."},
    {"symbol": "XLP",  "name": "Consumer Staples"},
    {"symbol": "XLB",  "name": "Materials"},
    {"symbol": "XLU",  "name": "Utilities"},
    {"symbol": "XLRE", "name": "Real Estate"},
    {"symbol": "XLC",  "name": "Communication Svcs"},
]

_CACHE_TTL_HOURS = 4


class MacroService:
    """Fetch macroeconomic indicators via yfinance with local cache."""

    def __init__(self, raw_data_dir: Path):
        self.cache_dir = raw_data_dir / "cache" / "macro"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._fetch_errors: list[dict] = []

    # ------------------------------------------------------------------
    # Cache helpers (mirrors MarketDataClient pattern)
    # ------------------------------------------------------------------

    def _cache_paths(self, symbol: str) -> tuple[Path, Path]:
        key = symbol.upper().replace("^", "").replace("=", "").replace(".", "").replace("-", "")
        return (
            self.cache_dir / f"{key}.csv",
            self.cache_dir / f"{key}.meta.json",
        )

    def _cache_is_fresh(self, meta_file: Path) -> bool:
        if not meta_file.exists():
            return False
        try:
            payload = json.loads(meta_file.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(payload["fetched_at"])
        except Exception:
            return False
        return fetched_at + timedelta(hours=_CACHE_TTL_HOURS) > datetime.now(timezone.utc)

    def _write_meta(self, meta_file: Path) -> None:
        meta_file.write_text(
            json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _fetch_history(self, symbol: str, period: str = "3mo") -> pd.DataFrame | None:
        csv_path, meta_path = self._cache_paths(symbol)

        if self._cache_is_fresh(meta_path) and csv_path.exists():
            try:
                df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
                if not df.empty:
                    return df
            except Exception:
                pass

        if yf is None:
            LOGGER.warning("yfinance not available; cannot fetch %s", symbol)
            return None

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1d", auto_adjust=True)
            if df is None or df.empty:
                LOGGER.warning("No data returned for macro symbol %s", symbol)
                self._fetch_errors.append({"symbol": symbol, "error": "No data returned", "stage": "macro"})
                return None
            df.to_csv(csv_path)
            self._write_meta(meta_path)
            return df
        except Exception as exc:
            LOGGER.warning("Failed to fetch macro symbol %s: %s", symbol, exc)
            self._fetch_errors.append({"symbol": symbol, "error": str(exc), "stage": "macro"})
            return None

    @staticmethod
    def _pct_change(df: pd.DataFrame, periods: int) -> float | None:
        col = "Close"
        if col not in df.columns or len(df) < periods + 1:
            return None
        try:
            latest = float(df[col].iloc[-1])
            prev = float(df[col].iloc[-(periods + 1)])
            if prev == 0:
                return None
            return round((latest - prev) / abs(prev), 6)
        except Exception:
            return None

    def _build_indicator(self, meta: dict, period: str) -> MacroIndicator:
        symbol = meta["symbol"]
        df = self._fetch_history(symbol, period=period)

        current_value: float | None = None
        change_1d: float | None = None
        change_1m: float | None = None
        change_3m: float | None = None

        if df is not None and not df.empty and "Close" in df.columns:
            current_value = round(float(df["Close"].iloc[-1]), 4)
            change_1d = self._pct_change(df, 1)
            # approx 1m = 21 trading days, 3m = 63
            change_1m = self._pct_change(df, min(21, len(df) - 1))
            change_3m = self._pct_change(df, min(63, len(df) - 1))

        return MacroIndicator(
            symbol=symbol,
            name=meta["name"],
            category=meta["category"],
            current_value=current_value,
            change_1d=change_1d,
            change_1m=change_1m,
            change_3m=change_3m,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_macro_context(self, run_date: str, period: str = "3mo") -> tuple[MacroContext, list[dict]]:
        """Fetch all macro indicators and return (MacroContext, fetch_errors)."""
        self._fetch_errors = []
        indicators: list[MacroIndicator] = []

        # Core macro indicators
        for meta in _INDICATORS:
            ind = self._build_indicator(meta, period=period)
            indicators.append(ind)

        # Sector ETFs
        sector_performance: dict[str, float] = {}
        for meta in _SECTOR_ETFS:
            ind = self._build_indicator({**meta, "category": "sector"}, period=period)
            indicators.append(ind)
            if ind.change_1m is not None:
                sector_performance[meta["name"]] = round(ind.change_1m * 100, 2)

        # Derived: yield curve spread (10Y - 3M), yield values are in % already for ^TNX/^IRX
        yield_curve_spread: float | None = None
        vix_level: float | None = None
        tnx = next((i for i in indicators if i.symbol == "^TNX"), None)
        irx = next((i for i in indicators if i.symbol == "^IRX"), None)
        vix = next((i for i in indicators if i.symbol == "^VIX"), None)

        if tnx and tnx.current_value is not None and irx and irx.current_value is not None:
            # ^TNX and ^IRX are reported as annualised % (e.g. 4.5 = 4.5%)
            # ^IRX is quoted in annualised discount rate; divide by 100 for same unit as ^TNX
            # Both are already in the same "percent" unit from yfinance
            yield_curve_spread = round(tnx.current_value - irx.current_value / 100, 4)
        if vix and vix.current_value is not None:
            vix_level = round(vix.current_value, 2)

        context = MacroContext(
            run_date=run_date,
            indicators=indicators,
            yield_curve_spread=yield_curve_spread,
            vix_level=vix_level,
            sector_performance=sector_performance,
        )
        return context, list(self._fetch_errors)
