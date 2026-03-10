from __future__ import annotations

import json
from pathlib import Path

from src.tickers.models import TickerProfile


class TickerRepository:
    """Load and filter ticker universe from static JSON configuration."""

    def __init__(self, source_path: Path):
        self.source_path = source_path

    def load_all(self) -> list[TickerProfile]:
        payload = json.loads(self.source_path.read_text(encoding="utf-8"))
        return [TickerProfile.model_validate(item) for item in payload]

    def load_symbols(self, limit: int | None = None) -> list[TickerProfile]:
        items = self.load_all()
        if limit is None:
            return items
        return items[:limit]

    def find_by_symbol(self, symbol: str) -> TickerProfile | None:
        normalized = symbol.upper()
        for ticker in self.load_all():
            if ticker.symbol.upper() == normalized:
                return ticker
        return None

    def remove_symbol(self, symbol: str) -> bool:
        """Permanently remove a ticker from the JSON file. Returns True if removed."""
        normalized = symbol.upper()
        raw = json.loads(self.source_path.read_text(encoding="utf-8"))
        before = len(raw)
        remaining = [item for item in raw if str(item.get("symbol", "")).upper() != normalized]
        if len(remaining) == before:
            return False  # not found
        self.source_path.write_text(
            json.dumps(remaining, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
