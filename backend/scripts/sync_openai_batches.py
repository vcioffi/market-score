from __future__ import annotations

import argparse
import json
import sys

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.llm.sync import OpenAIBatchSyncService
from src.utils.logging import configure_logging


def _parse_batch_ids(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    values = {item.strip() for item in raw.split(",") if item.strip()}
    return values or None


def main() -> None:
    parser = argparse.ArgumentParser(description="List and sync OpenAI batch jobs submitted by Market Score")
    parser.add_argument("--run-date", type=str, default=None, help="Filter by run date (YYYY-MM-DD)")
    parser.add_argument("--batch-ids", type=str, default=None, help="Comma-separated batch IDs to sync")
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list registry entries without checking remote OpenAI status",
    )
    parser.add_argument(
        "--include-downloaded",
        action="store_true",
        help="Include already-downloaded entries",
    )
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="Refresh all statuses, including terminal states",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    service = OpenAIBatchSyncService(settings)
    imported = service.import_legacy_metadata()

    if args.list_only:
        entries = service.list_entries(
            run_date=args.run_date,
            include_downloaded=args.include_downloaded,
        )
        print(
            json.dumps(
                {
                    "imported_legacy": imported,
                    "count": len(entries),
                    "entries": entries,
                },
                indent=2,
            )
        )
        return

    try:
        result = service.sync(
            run_date=args.run_date,
            batch_ids=_parse_batch_ids(args.batch_ids),
            include_downloaded=args.include_downloaded,
            refresh_all=args.refresh_all,
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc

    print(
        json.dumps(
            {
                "status": "ok",
                "imported_legacy": imported,
                **result,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
