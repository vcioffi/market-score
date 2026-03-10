from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OpenAIBatchRegistry:
    """Track OpenAI batch jobs lifecycle and download state."""

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_store(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"batches": []}
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.warning("Batch registry is invalid JSON, recreating: %s", self.registry_path)
            return {"batches": []}

        if not isinstance(payload, dict):
            return {"batches": []}
        if not isinstance(payload.get("batches"), list):
            payload["batches"] = []
        return payload

    def _save_store(self, payload: dict[str, Any]) -> None:
        payload["updated_at"] = utc_now_iso()
        self.registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, batch_id: str) -> dict[str, Any] | None:
        store = self._load_store()
        for entry in store["batches"]:
            if entry.get("batch_id") == batch_id:
                return entry
        return None

    def upsert(self, entry: dict[str, Any]) -> dict[str, Any]:
        if not entry.get("batch_id"):
            raise ValueError("batch_id is required")

        store = self._load_store()
        entry = dict(entry)
        entry.setdefault("submitted_at", utc_now_iso())
        entry.setdefault("updated_at", utc_now_iso())
        entry.setdefault("downloaded", False)

        for idx, existing in enumerate(store["batches"]):
            if existing.get("batch_id") == entry["batch_id"]:
                merged = {**existing, **entry, "updated_at": utc_now_iso()}
                store["batches"][idx] = merged
                self._save_store(store)
                return merged

        store["batches"].append(entry)
        self._save_store(store)
        return entry

    def update(self, batch_id: str, **updates: Any) -> dict[str, Any] | None:
        store = self._load_store()
        for idx, existing in enumerate(store["batches"]):
            if existing.get("batch_id") == batch_id:
                merged = {**existing, **updates, "updated_at": utc_now_iso()}
                store["batches"][idx] = merged
                self._save_store(store)
                return merged
        return None

    def list_entries(
        self,
        statuses: set[str] | None = None,
        downloaded: bool | None = None,
        run_date: str | None = None,
    ) -> list[dict[str, Any]]:
        store = self._load_store()
        entries = list(store["batches"])

        if statuses is not None:
            entries = [item for item in entries if item.get("status") in statuses]
        if downloaded is not None:
            entries = [item for item in entries if bool(item.get("downloaded")) == downloaded]
        if run_date is not None:
            entries = [item for item in entries if item.get("run_date") == run_date]

        entries.sort(key=lambda item: item.get("submitted_at", ""), reverse=True)
        return entries

    def ensure_from_metadata(self, processed_dir: Path) -> int:
        """Import batch ids from run metadata files when registry was not active yet."""

        imported = 0
        for path in processed_dir.glob("*/llm/metadata.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if payload.get("mode") != "openai_batch":
                continue

            batch_id = payload.get("batch_id")
            if not batch_id:
                continue
            if self.get(batch_id):
                continue

            run_date = path.parts[-3]
            self.upsert(
                {
                    "batch_id": batch_id,
                    "pipeline": "ticker_analysis",
                    "run_date": run_date,
                    "status": payload.get("status", "unknown"),
                    "completion_window": payload.get("completion_window"),
                    "source": "metadata_import",
                }
            )
            imported += 1

        return imported
