from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.pipelines.weekly_summary_pipeline import WeeklySummaryPipeline
from src.storage.json_store import JsonStorage
from src.utils.dates import today_iso
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly ranking summary from ticker outputs")
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument(
        "--no-wait-for-batch",
        action="store_true",
        help="Do not wait for OpenAI weekly batch completion",
    )
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode (OpenAI enabled)")
    parser.add_argument("--openai-news-research", action="store_true", help="Unused in this script; kept for CLI consistency")
    parser.add_argument(
        "--live-no-batch",
        action="store_true",
        help="Disable dry-run and use synchronous OpenAI call (no batch queue)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.live_no_batch:
        settings.dry_run = False
        settings.openai_use_batch = False
    else:
        settings.dry_run = not args.live

    configure_logging(settings.log_level)

    run_date = args.run_date or today_iso(settings.timezone)

    storage = JsonStorage(settings.raw_data_dir, settings.processed_data_dir, settings.outputs_data_dir)
    pipeline = WeeklySummaryPipeline(settings, storage)
    result = pipeline.run(run_date=run_date, wait_for_batch=not args.no_wait_for_batch)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
