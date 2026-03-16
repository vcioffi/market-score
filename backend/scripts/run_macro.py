from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.pipelines.macro_pipeline import MacroPipeline
from src.storage.json_store import JsonStorage
from src.utils.dates import today_iso
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run macroeconomic analysis pipeline")
    parser.add_argument("--run-date", type=str, default=None, help="ISO date for this run, e.g. 2026-03-07")
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode (use OpenAI for LLM analysis)")
    parser.add_argument(
        "--live-no-batch",
        action="store_true",
        help="Disable dry-run and use synchronous OpenAI calls",
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
    storage = JsonStorage(
        raw_dir=settings.raw_data_dir,
        processed_dir=settings.processed_data_dir,
        outputs_dir=settings.outputs_data_dir,
    )

    result = MacroPipeline(settings, storage).run(run_date=run_date)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
