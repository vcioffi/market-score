from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


class JsonStorage:
    """Filesystem persistence for raw, processed and final output artifacts."""

    def __init__(self, raw_dir: Path, processed_dir: Path, outputs_dir: Path):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.outputs_dir = outputs_dir

    def _run_dir(self, base: Path, run_date: str) -> Path:
        path = base / run_date
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_history(self, run_date: str, symbol: str, history: pd.DataFrame) -> Path:
        folder = self._run_dir(self.raw_dir, run_date) / "market_data"
        folder.mkdir(parents=True, exist_ok=True)
        file_path = folder / f"{symbol.upper()}.csv"

        frame = history.copy()
        if frame.index.name != "Date":
            frame.index.name = "Date"
        frame.to_csv(file_path)
        return file_path

    def load_history(self, run_date: str, symbol: str) -> pd.DataFrame:
        file_path = self.raw_dir / run_date / "market_data" / f"{symbol.upper()}.csv"
        frame = pd.read_csv(file_path)
        date_col = "Date" if "Date" in frame.columns else frame.columns[0]
        frame[date_col] = pd.to_datetime(frame[date_col])
        if date_col != "Date":
            frame = frame.rename(columns={date_col: "Date"})
        return frame.set_index("Date")

    def save_fundamentals(self, run_date: str, symbol: str, payload: dict) -> Path:
        folder = self._run_dir(self.raw_dir, run_date) / "fundamentals"
        folder.mkdir(parents=True, exist_ok=True)
        file_path = folder / f"{symbol.upper()}.json"
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return file_path

    def load_fundamentals(self, run_date: str, symbol: str) -> dict:
        file_path = self.raw_dir / run_date / "fundamentals" / f"{symbol.upper()}.json"
        if not file_path.exists():
            return {}
        return json.loads(file_path.read_text(encoding="utf-8"))

    def save_processed_metrics(self, run_date: str, symbol: str, payload: dict) -> Path:
        folder = self._run_dir(self.processed_dir, run_date) / "metrics"
        folder.mkdir(parents=True, exist_ok=True)
        file_path = folder / f"{symbol.upper()}.json"
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return file_path

    def load_processed_metrics(self, run_date: str, symbol: str) -> dict:
        file_path = self.processed_dir / run_date / "metrics" / f"{symbol.upper()}.json"
        return json.loads(file_path.read_text(encoding="utf-8"))

    def save_news_context(self, run_date: str, symbol: str, payload: dict) -> Path:
        folder = self._run_dir(self.processed_dir, run_date) / "news"
        folder.mkdir(parents=True, exist_ok=True)
        file_path = folder / f"{symbol.upper()}.json"
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return file_path

    def load_news_context(self, run_date: str, symbol: str) -> dict:
        file_path = self.processed_dir / run_date / "news" / f"{symbol.upper()}.json"
        if not file_path.exists():
            return {"company_news": [], "sector_news": []}
        return json.loads(file_path.read_text(encoding="utf-8"))

    def save_ticker_output(self, run_date: str, symbol: str, payload: dict) -> Path:
        folder = self._run_dir(self.outputs_dir, run_date)
        file_path = folder / f"{symbol.upper()}.json"
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return file_path

    def load_ticker_output(self, run_date: str, symbol: str) -> dict:
        file_path = self.outputs_dir / run_date / f"{symbol.upper()}.json"
        return json.loads(file_path.read_text(encoding="utf-8"))

    def save_weekly_summary(self, run_date: str, payload: dict) -> Path:
        folder = self._run_dir(self.outputs_dir, run_date)
        file_path = folder / "weekly_summary.json"
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return file_path

    def load_weekly_summary(self, run_date: str) -> dict:
        file_path = self.outputs_dir / run_date / "weekly_summary.json"
        return json.loads(file_path.read_text(encoding="utf-8"))

    def list_run_dates(self) -> list[str]:
        if not self.outputs_dir.exists():
            return []
        return sorted([item.name for item in self.outputs_dir.iterdir() if item.is_dir()])

    def latest_run_date(self) -> str | None:
        runs = self.list_run_dates()
        return runs[-1] if runs else None

    def list_ticker_output_files(self, run_date: str) -> list[Path]:
        run_dir = self.outputs_dir / run_date
        if not run_dir.exists():
            return []
        return sorted(
            [item for item in run_dir.glob("*.json") if item.name.lower() != "weekly_summary.json"]
        )

    def save_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
