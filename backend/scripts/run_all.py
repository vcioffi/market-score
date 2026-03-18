from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.pipelines.run_all_pipeline import FullPipeline
from src.utils.dates import today_iso
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full Market Score pipeline")
    parser.add_argument("--run-date", type=str, default=None, help="ISO date for this run, example 2026-03-07")
    parser.add_argument("--period", type=str, default=None, help="History period: 6mo, 1y, 3y, 5y")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols, example AAPL,MSFT")
    parser.add_argument(
        "--no-wait-for-batch",
        action="store_true",
        help="Do not wait for OpenAI batch completion; returns provisional fallback outputs",
    )
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache and refresh market data")
    parser.add_argument("--openai-news-research", action="store_true", help="Use OpenAI web search research for news context")
    parser.add_argument(
        "--openai-news-model",
        type=str,
        default=None,
        help="Override model used for OpenAI news research (example: gpt-5, o4-mini-deep-research)",
    )
    parser.add_argument(
        "--news-workers",
        type=int,
        default=None,
        help="Parallel workers for OpenAI news research (default 1=sequential, suggested 5 for standard, 3 for deep-research)",
    )
    parser.add_argument(
        "--static",
        action="store_true",
        help=(
            "Run static (no-LLM) analysis: fetches real market data and news, "
            "computes all scores and narratives deterministically — zero API cost"
        ),
    )
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode (LLM enabled)")
    parser.add_argument(
        "--live-no-batch",
        action="store_true",
        help="Disable dry-run and use synchronous LLM calls (no batch queue, immediate results)",
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Skip news pipeline entirely (reuse already-saved news context from disk)",
    )
    parser.add_argument(
        "--llm-only",
        action="store_true",
        help="Skip market data, metrics, and news pipelines — run only LLM analysis on saved data",
    )
    parser.add_argument(
        "--skip-macro",
        action="store_true",
        help="Skip the macroeconomic analysis pipeline",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.static:
        settings.dry_run = False
        settings.analysis_mode = "static"
    elif args.live_no_batch:
        settings.dry_run = False
        settings.openai_use_batch = False
    else:
        settings.dry_run = not args.live

    if args.openai_news_research:
        settings.openai_news_research_enabled = True
    if args.openai_news_model:
        settings.openai_model_news = args.openai_news_model.strip()
        settings.openai_news_research_enabled = True
    if args.news_workers is not None:
        settings.openai_news_workers = args.news_workers

    configure_logging(settings.log_level)

    run_date = args.run_date or today_iso(settings.timezone)
    wait_for_batch = not args.no_wait_for_batch
    symbols = [item.strip().upper() for item in args.symbols.split(",")] if args.symbols else None

    result = FullPipeline(settings).run_all(
        run_date=run_date,
        period=args.period,
        wait_for_batch=wait_for_batch,
        force_refresh=args.force_refresh,
        symbols=symbols,
        skip_news=args.skip_news or args.llm_only,
        skip_market=args.llm_only,
        skip_macro=args.skip_macro,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
