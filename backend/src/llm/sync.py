from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from src.config.settings import Settings
from src.llm.batch import OpenAIBatchManager, extract_message_content
from src.llm.fallback import parse_json_from_model_output
from src.llm.registry import OpenAIBatchRegistry, utc_now_iso
from src.llm.schemas import TickerAnalysis, TickerAnalysisLLM, WeeklySummary
from src.portfolio.ranking import build_weekly_summary
from src.storage.json_store import JsonStorage
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)

FINAL_FAILURE_STATUSES = {"failed", "expired", "cancelled"}


class OpenAIBatchSyncService:
    """Sync statuses and download completed OpenAI batch results into local artifacts."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = OpenAIBatchRegistry(settings.openai_batch_registry_path)
        self.storage = JsonStorage(settings.raw_data_dir, settings.processed_data_dir, settings.outputs_data_dir)

    def _manager(self) -> OpenAIBatchManager:
        if not self.settings.openai_api_key:
            raise RuntimeError("MARKET_SCORE_OPENAI_API_KEY is required for batch sync")
        return OpenAIBatchManager(
            api_key=self.settings.openai_api_key,
            completion_window=self.settings.openai_completion_window,
        )

    def import_legacy_metadata(self) -> int:
        return self.registry.ensure_from_metadata(self.settings.processed_data_dir)

    def list_entries(self, run_date: str | None = None, include_downloaded: bool = True) -> list[dict[str, Any]]:
        downloaded_filter = None if include_downloaded else False
        return self.registry.list_entries(run_date=run_date, downloaded=downloaded_filter)

    def _apply_ticker_batch_output(self, run_date: str, output_lines: list[dict]) -> dict[str, int]:
        saved = 0
        invalid = 0

        for line in output_lines:
            custom_id = str(line.get("custom_id") or "")
            fallback_symbol = custom_id.split(":")[-1].upper() if ":" in custom_id else custom_id.upper()
            try:
                content = extract_message_content(line)
                payload = parse_json_from_model_output(content)
                # Try compact LLM schema first, then fall back to full schema for backwards compat
                try:
                    llm_model = TickerAnalysisLLM.model_validate(payload)
                    symbol = (llm_model.ticker or fallback_symbol).upper()
                    # Try to enrich with stored pipeline data
                    try:
                        metrics = self.storage.load_processed_metrics(run_date=run_date, symbol=symbol)
                    except Exception:
                        metrics = {}
                    full_model = TickerAnalysis(
                        **llm_model.model_dump(),
                        quant_metrics=metrics.get("quant", {}),
                        fundamentals=metrics.get("fundamentals", {}),
                        price_history=metrics.get("price_history", []),
                    )
                except ValidationError:
                    # Fall back to full schema (handles outputs produced before this refactor)
                    full_model = TickerAnalysis.model_validate(payload)
                    symbol = (full_model.ticker or fallback_symbol).upper()

                self.storage.save_ticker_output(run_date=run_date, symbol=symbol, payload=full_model.model_dump(mode="json"))
                saved += 1
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                invalid += 1
                LOGGER.warning("Invalid ticker batch output for %s: %s", fallback_symbol or "unknown", exc)

        return {"saved": saved, "invalid": invalid}

    def _apply_weekly_batch_output(self, run_date: str, output_lines: list[dict]) -> bool:
        if not output_lines:
            return False

        line = output_lines[0]
        content = extract_message_content(line)
        payload = parse_json_from_model_output(content)
        model = WeeklySummary.model_validate(payload)

        # Keep deterministic ranking output as source of truth and only enrich commentary.
        self._rebuild_weekly_summary(run_date)

        if model.llm_commentary:
            weekly_path = self.settings.outputs_data_dir / run_date / "weekly_summary.json"
            weekly_payload = self.storage.load_json(weekly_path)
            weekly_payload["llm_commentary"] = model.llm_commentary
            self.storage.save_weekly_summary(run_date=run_date, payload=weekly_payload)

        return True

    def _rebuild_weekly_summary(self, run_date: str) -> None:
        files = self.storage.list_ticker_output_files(run_date=run_date)
        analyses: list[TickerAnalysis] = []
        for path in files:
            try:
                analyses.append(TickerAnalysis.model_validate(self.storage.load_json(path)))
            except Exception as exc:
                LOGGER.warning("Skipping invalid ticker artifact %s: %s", path.name, exc)

        summary = build_weekly_summary(run_date=run_date, analyses=analyses)

        existing_weekly = self.settings.outputs_data_dir / run_date / "weekly_summary.json"
        if existing_weekly.exists():
            try:
                existing_payload = self.storage.load_json(existing_weekly)
                commentary = existing_payload.get("llm_commentary")
                if commentary:
                    summary.llm_commentary = commentary
            except Exception:
                pass

        self.storage.save_weekly_summary(run_date=run_date, payload=summary.model_dump(mode="json"))

    def _extract_error_messages(self, error_text: str, max_messages: int = 3) -> list[str]:
        messages: list[str] = []
        seen: set[str] = set()
        for raw_line in error_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            message: str | None = None
            try:
                payload = json.loads(line)
                response_error = ((payload.get("response") or {}).get("body") or {}).get("error") or {}
                message = response_error.get("message")
                if not message and payload.get("error"):
                    message = str(payload.get("error"))
            except json.JSONDecodeError:
                message = line

            if not message:
                continue

            normalized = message.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            messages.append(normalized)
            if len(messages) >= max_messages:
                break

        return messages

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def sync(
        self,
        run_date: str | None = None,
        batch_ids: set[str] | None = None,
        include_downloaded: bool = False,
        refresh_all: bool = False,
    ) -> dict[str, Any]:
        # If specific batch IDs are requested, include downloaded entries too.
        downloaded_filter = None if (include_downloaded or batch_ids) else False
        entries = self.registry.list_entries(run_date=run_date, downloaded=downloaded_filter)
        if batch_ids:
            entries = [entry for entry in entries if str(entry.get("batch_id")) in batch_ids]

        if not refresh_all:
            allowed = {
                "submitted",
                "submitted_pending",
                "validating",
                "in_progress",
                "finalizing",
                "completed",
                "unknown",
                None,
            }
            entries = [entry for entry in entries if entry.get("status") in allowed]

        if not entries:
            return {"checked": 0, "downloaded": 0, "updated": []}

        manager = self._manager()

        downloaded = 0
        checked = 0
        updated: list[dict[str, Any]] = []
        rebuild_runs: set[str] = set()

        for entry in entries:
            batch_id = str(entry.get("batch_id") or "")
            pipeline = str(entry.get("pipeline") or "")
            batch_run_date = str(entry.get("run_date") or "")
            if not batch_id or not pipeline or not batch_run_date:
                continue

            checked += 1
            try:
                remote = manager.get_batch(batch_id)
            except Exception as exc:
                self.registry.update(batch_id, last_check_error=str(exc), last_checked_at=utc_now_iso())
                updated.append({"batch_id": batch_id, "status": "check_failed", "error": str(exc)})
                continue

            status = str(remote.get("status") or "unknown")
            output_file_id = remote.get("output_file_id")
            error_file_id = remote.get("error_file_id")

            request_counts = remote.get("request_counts") or {}
            completed_count = self._safe_int(request_counts.get("completed"))
            failed_count = self._safe_int(request_counts.get("failed"))
            total_count = self._safe_int(request_counts.get("total"))

            self.registry.update(
                batch_id,
                status=status,
                output_file_id=output_file_id,
                error_file_id=error_file_id,
                request_counts={
                    "completed": completed_count,
                    "failed": failed_count,
                    "total": total_count,
                },
                last_checked_at=utc_now_iso(),
            )

            entry_result: dict[str, Any] = {
                "batch_id": batch_id,
                "status": status,
                "pipeline": pipeline,
                "request_counts": {
                    "completed": completed_count,
                    "failed": failed_count,
                    "total": total_count,
                },
            }

            if status == "completed" and output_file_id and not bool(entry.get("downloaded")):
                try:
                    lines = manager.download_output_lines(str(output_file_id))
                    if pipeline == "ticker_analysis":
                        counts = self._apply_ticker_batch_output(batch_run_date, lines)
                        entry_result.update(counts)
                        rebuild_runs.add(batch_run_date)
                        parsed_items = counts["saved"]
                    elif pipeline == "weekly_summary":
                        ok = self._apply_weekly_batch_output(batch_run_date, lines)
                        entry_result["saved"] = 1 if ok else 0
                        parsed_items = 1 if ok else 0
                    else:
                        entry_result["saved"] = 0
                        parsed_items = 0

                    self.registry.update(
                        batch_id,
                        downloaded=True,
                        downloaded_at=utc_now_iso(),
                        parsed_items=parsed_items,
                    )
                    downloaded += 1
                except Exception as exc:
                    self.registry.update(batch_id, download_error=str(exc), download_failed_at=utc_now_iso())
                    entry_result["download_error"] = str(exc)

            elif status == "completed" and not output_file_id and failed_count > 0:
                failure_messages: list[str] = []
                if error_file_id:
                    try:
                        error_text = manager.download_file_text(str(error_file_id))
                        failure_messages = self._extract_error_messages(error_text)
                    except Exception as exc:
                        failure_messages = [f"Unable to download error file: {exc}"]

                self.registry.update(
                    batch_id,
                    finalized_at=utc_now_iso(),
                    failure_messages=failure_messages,
                    has_only_failed_requests=completed_count == 0 and failed_count > 0,
                    downloaded=True,
                    downloaded_at=utc_now_iso(),
                )
                entry_result["failure_messages"] = failure_messages
                entry_result["has_only_failed_requests"] = completed_count == 0 and failed_count > 0

            elif status == "completed" and not output_file_id:
                self.registry.update(
                    batch_id,
                    finalized_at=utc_now_iso(),
                    downloaded=True,
                    downloaded_at=utc_now_iso(),
                )
                entry_result["note"] = "completed_without_output_file"

            elif status in FINAL_FAILURE_STATUSES:
                self.registry.update(
                    batch_id,
                    finalized_at=utc_now_iso(),
                    downloaded=True,
                    downloaded_at=utc_now_iso(),
                )

            updated.append(entry_result)

        for affected_run in sorted(rebuild_runs):
            try:
                self._rebuild_weekly_summary(affected_run)
            except Exception as exc:
                LOGGER.warning("Failed to rebuild weekly summary for %s: %s", affected_run, exc)

        return {
            "checked": checked,
            "downloaded": downloaded,
            "updated": updated,
            "rebuilt_runs": sorted(rebuild_runs),
        }

