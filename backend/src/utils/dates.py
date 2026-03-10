from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def today_iso(timezone: str) -> str:
    """Return current date in ISO format for the configured timezone."""

    return datetime.now(ZoneInfo(timezone)).date().isoformat()
