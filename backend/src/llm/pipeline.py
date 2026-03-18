from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from src.config.settings import Settings
from src.llm.batch import (
    BatchRequest,
    OpenAIBatchManager,
    OpenAIDirectManager,
    extract_chat_completion_content,
    extract_message_content,
)
from src.llm.fallback import build_fallback_ticker_analysis, parse_json_from_model_output
from src.llm.prompts import (
    build_macro_system_prompt,
    build_macro_user_prompt,
    build_ticker_system_prompt,
    build_ticker_user_prompt,
    build_weekly_commentary_prompt,
    build_weekly_system_prompt,
    build_weekly_user_prompt,
)
from src.llm.registry import OpenAIBatchRegistry, utc_now_iso
from src.llm.schemas import MacroAnalysis, MacroAnalysisLLM, TickerAnalysis, TickerAnalysisLLM, WeeklyLLMCommentary, WeeklySummary
from src.tickers.models import TickerProfile
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


@dataclass
class TickerLLMInput:
    profile: TickerProfile
    metrics_payload: dict
    news_payload: dict

    def to_prompt_payload(self) -> dict:
        quant = self.metrics_payload.get("quant", {})
        fund = self.metrics_payload.get("fundamentals", {})

        def r(v, d=3):
            try:
                return round(float(v), d) if v is not None else None
            except (TypeError, ValueError):
                return None

        # MA distances (% vs current price) — more useful than absolute MA values
        latest = quant.get("latest_close")
        mas = quant.get("moving_averages", {})

        def ma_dist(ma_val):
            try:
                return r((float(latest) / float(ma_val)) - 1) if latest and ma_val else None
            except (TypeError, ValueError, ZeroDivisionError):
                return None

        compact_quant = {
            "ret_1m": r(quant.get("returns", {}).get("1m"), 4),
            "ret_3m": r(quant.get("returns", {}).get("3m"), 4),
            "ret_1y": r(quant.get("returns", {}).get("1y"), 4),
            "vol": r(quant.get("rolling_volatility_20d")),
            "drawdown": r(quant.get("max_drawdown")),
            "sharpe": r(quant.get("sharpe_ratio")),
            "beta": r(quant.get("beta")),
            "rsi": r(quant.get("rsi_14")),
            "vs_ma20": ma_dist(mas.get("ma_20")),
            "vs_ma50": ma_dist(mas.get("ma_50")),
            "vs_ma200": ma_dist(mas.get("ma_200")),
            "dist_52w_hi": r(quant.get("distance_recent_high")),
            "price": r(latest),
            "breakout": quant.get("signals", {}).get("breakout"),
            "vol_squeeze": quant.get("signals", {}).get("volatility_compression"),
        }

        compact_fund = {
            "pe": r(fund.get("pe")),
            "fwd_pe": r(fund.get("forward_pe")),
            "rev_gr": r(fund.get("revenue_growth")),
            "op_margin": r(fund.get("operating_margin")),
            "ebitda_margin": r(fund.get("ebitda_margin")),
            "eps_gr": r(fund.get("eps_growth")),
            "eps": r(fund.get("trailing_eps")),
            "d_e": r(fund.get("debt_to_equity")),
            "mcap_b": r((fund.get("market_cap") or 0) / 1e9, 1),
            # Graham-style metrics
            "roe": r(fund.get("roe")),
            "pb": r(fund.get("pb_ratio")),
            "curr_ratio": r(fund.get("current_ratio")),
            "quick_ratio": r(fund.get("quick_ratio")),
            "bvps": r(fund.get("book_value_per_share")),
            "graham_num": r(fund.get("graham_number")),
            "mos_pct": r(fund.get("margin_of_safety")),
            "div_yield": r(fund.get("dividend_yield")),
        }

        # 3 articles max, short title+summary only
        def _compact_articles(articles: list) -> list:
            out = []
            for a in articles[:3]:
                if isinstance(a, dict):
                    out.append({
                        "t": (a.get("title") or "")[:80],
                        "s": (a.get("summary") or "")[:150],
                    })
            return out

        return {
            "ticker": self.profile.symbol,
            "company": self.profile.company_name,
            "sector": self.profile.sector,
            "industry": self.profile.industry,
            "quant": compact_quant,
            "fund": compact_fund,
            "co_news": _compact_articles(self.news_payload.get("company_news", [])),
            "sec_news": _compact_articles(self.news_payload.get("sector_news", [])),
        }


class TickerLLMAnalysisEngine:
    """Run per-ticker analysis with OpenAI batch/direct mode, with deterministic fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = OpenAIBatchRegistry(settings.openai_batch_registry_path)

    def _build_batch_requests(self, inputs: list[TickerLLMInput], run_date: str) -> list[BatchRequest]:
        # Use the compact LLM schema (no price_history/quant_metrics/fundamentals)
        schema = TickerAnalysisLLM.model_json_schema()
        return [
            BatchRequest(
                custom_id=f"{run_date}:{entry.profile.symbol}",
                model=self.settings.effective_llm_model_ticker,
                system_prompt=build_ticker_system_prompt(),
                user_prompt=build_ticker_user_prompt(entry.to_prompt_payload()),
                json_schema_name="ticker_analysis",
                json_schema=schema,
                max_completion_tokens=self.settings.openai_ticker_max_completion_tokens,
            )
            for entry in inputs
        ]

    def _merge_pipeline_data(self, llm_model: TickerAnalysisLLM, entry: TickerLLMInput) -> TickerAnalysis:
        """Merge LLM output with pipeline-supplied market data."""
        return TickerAnalysis(
            ticker=llm_model.ticker,
            company_name=llm_model.company_name,
            sector=llm_model.sector,
            industry=llm_model.industry,
            quant_summary=llm_model.quant_summary,
            qualitative_summary=llm_model.qualitative_summary,
            key_positive_factors=llm_model.key_positive_factors,
            key_negative_factors=llm_model.key_negative_factors,
            news_sentiment_score=llm_model.news_sentiment_score,
            risk_score=llm_model.risk_score,
            benefit_score=llm_model.benefit_score,
            confidence_score=llm_model.confidence_score,
            investment_view=llm_model.investment_view,
            time_horizon=llm_model.time_horizon,
            monitoring_triggers=llm_model.monitoring_triggers,
            short_advice=llm_model.short_advice,
            sources_used=llm_model.sources_used,
            quant_metrics=entry.metrics_payload.get("quant", {}),
            fundamentals=entry.metrics_payload.get("fundamentals", {}),
            fundamental_analysis=llm_model.fundamental_analysis,
            price_history=entry.metrics_payload.get("price_history", []),
            # timestamp uses TickerAnalysis.default_factory (pipeline sets it, not the LLM)
        )

    def _fallback_map(self, inputs: list[TickerLLMInput]) -> dict[str, TickerAnalysis]:
        results: dict[str, TickerAnalysis] = {}
        for entry in inputs:
            results[entry.profile.symbol] = build_fallback_ticker_analysis(
                profile=entry.profile,
                metrics_payload=entry.metrics_payload,
                news_payload=entry.news_payload,
                sources_used=entry.news_payload.get("sources_used", []) + ["deterministic_fallback"],
            )
        return results

    def _run_direct(
        self,
        inputs: list[TickerLLMInput],
        fallback_results: dict[str, TickerAnalysis],
        on_ticker_done: object = None,
    ) -> tuple[dict[str, TickerAnalysis], dict]:
        try:
            manager = OpenAIDirectManager(
                api_key=self.settings.effective_llm_api_key,
                base_url=self.settings.effective_llm_base_url,
                use_json_schema=self.settings.llm_use_json_schema,
            )
        except Exception as exc:
            LOGGER.warning("OpenAI direct mode init failed, falling back: %s", exc)
            return fallback_results, {"mode": "fallback", "reason": "openai_direct_init_failed", "error": str(exc)}

        # Use compact LLM schema (no price_history/quant_metrics/fundamentals)
        schema = TickerAnalysisLLM.model_json_schema()
        # Build a lookup from symbol -> entry for data merging after parse
        entry_by_symbol = {e.profile.symbol.upper(): e for e in inputs}
        parsed: dict[str, TickerAnalysis] = {}
        errors: dict[str, str] = {}

        def _request_and_parse(request: BatchRequest, entry: TickerLLMInput) -> TickerAnalysis:
            response_payload = manager.create_chat_completion(request)
            content = extract_chat_completion_content(response_payload)
            payload = parse_json_from_model_output(content)
            llm_model = TickerAnalysisLLM.model_validate(payload)
            return self._merge_pipeline_data(llm_model, entry)

        for entry in inputs:
            symbol = entry.profile.symbol.upper()
            request = BatchRequest(
                custom_id=symbol,
                model=self.settings.effective_llm_model_ticker,
                system_prompt=build_ticker_system_prompt(),
                user_prompt=build_ticker_user_prompt(entry.to_prompt_payload()),
                json_schema_name="ticker_analysis",
                json_schema=schema,
                max_completion_tokens=self.settings.openai_ticker_max_completion_tokens,
            )

            try:
                parsed_model = _request_and_parse(request, entry)
            except (ValueError, ValidationError, json.JSONDecodeError) as first_exc:
                LOGGER.warning("Invalid direct model output for %s (attempt 1): %s", symbol, first_exc)
                # On token length errors, retry with more tokens (not more prompt text).
                # On other errors (bad JSON, validation), retry with clarifying instruction.
                is_length_error = "finish_reason='length'" in str(first_exc)
                base_tokens = self.settings.openai_ticker_max_completion_tokens or 1500
                retry_tokens = min(base_tokens * 2, 4000) if is_length_error else base_tokens
                retry_prompt = (
                    request.user_prompt
                    if is_length_error
                    else request.user_prompt
                    + "\n\nIMPORTANT: Return a single valid JSON object only. No markdown, no prose, no code fences."
                )
                retry_request = BatchRequest(
                    custom_id=symbol,
                    model=self.settings.openai_model_ticker,
                    system_prompt=build_ticker_system_prompt(),
                    user_prompt=retry_prompt,
                    json_schema_name="ticker_analysis",
                    json_schema=schema,
                    max_completion_tokens=retry_tokens,
                )
                try:
                    parsed_model = _request_and_parse(retry_request, entry)
                except (ValueError, ValidationError, json.JSONDecodeError) as retry_exc:
                    LOGGER.warning("Invalid direct model output for %s (attempt 2): %s", symbol, retry_exc)
                    errors[symbol] = str(retry_exc)
                    continue
                except Exception as retry_exc:
                    LOGGER.warning("Direct model request failed for %s (attempt 2): %s", symbol, retry_exc)
                    errors[symbol] = str(retry_exc)
                    continue
            except Exception as exc:
                LOGGER.warning("Direct model request failed for %s: %s", symbol, exc)
                errors[symbol] = str(exc)
                continue

            parsed_symbol = parsed_model.ticker.upper() if parsed_model.ticker else symbol
            parsed[parsed_symbol] = parsed_model
            # Save immediately so progress is not lost on interruption
            if callable(on_ticker_done):
                try:
                    on_ticker_done(parsed_symbol, parsed_model)
                except Exception as save_exc:
                    LOGGER.warning("Failed to save ticker %s immediately: %s", parsed_symbol, save_exc)

        fallback_results.update(parsed)
        metadata: dict[str, object] = {
            "mode": "openai_direct",
            "status": "completed",
            "processed": len(parsed),
            "failed": len(inputs) - len(parsed),
        }
        if errors:
            metadata["errors"] = errors

        return fallback_results, metadata

    def _run_batch(
        self,
        inputs: list[TickerLLMInput],
        run_date: str,
        artifacts_dir: Path,
        wait_for_batch: bool,
        fallback_results: dict[str, TickerAnalysis],
    ) -> tuple[dict[str, TickerAnalysis], dict]:
        try:
            manager = OpenAIBatchManager(
                api_key=str(self.settings.openai_api_key),
                completion_window=self.settings.openai_completion_window,
            )
            requests = self._build_batch_requests(inputs, run_date)
            jsonl_path = artifacts_dir / "ticker_analysis_batch.jsonl"
            manager.write_requests_jsonl(requests, jsonl_path)
            job = manager.submit_batch(
                jsonl_path,
                metadata={"pipeline": "ticker_analysis", "run_date": run_date},
            )
        except Exception as exc:
            LOGGER.warning("OpenAI batch submission failed, falling back: %s", exc)
            return fallback_results, {
                "mode": "fallback",
                "reason": "openai_batch_submission_failed",
                "error": str(exc),
            }

        batch_id = str(job.get("id"))
        initial_status = str(job.get("status") or "submitted")
        self.registry.upsert(
            {
                "batch_id": batch_id,
                "pipeline": "ticker_analysis",
                "run_date": run_date,
                "status": initial_status,
                "completion_window": self.settings.openai_completion_window,
                "symbols": [item.profile.symbol for item in inputs],
                "artifacts_dir": str(artifacts_dir),
                "submitted_at": utc_now_iso(),
                "downloaded": False,
            }
        )

        metadata = {
            "mode": "openai_batch",
            "batch_id": batch_id,
            "status": "submitted_pending" if not wait_for_batch else initial_status,
            "completion_window": self.settings.openai_completion_window,
        }

        if not wait_for_batch:
            self.registry.update(batch_id, status="submitted_pending")
            LOGGER.info("Batch submitted without waiting. Returning provisional fallback output.")
            for payload in fallback_results.values():
                payload.sources_used.append(f"openai_batch_submitted:{batch_id}")
            return fallback_results, metadata

        try:
            batch = manager.wait_for_completion(
                batch_id=batch_id,
                max_wait_minutes=self.settings.openai_max_wait_minutes,
                poll_seconds=self.settings.openai_poll_interval_seconds,
            )
        except Exception as exc:
            LOGGER.warning("OpenAI batch wait failed, falling back: %s", exc)
            metadata["status"] = "wait_failed"
            metadata["error"] = str(exc)
            self.registry.update(batch_id, status="wait_failed", error=str(exc))
            return fallback_results, metadata

        status = str(batch.get("status") or "unknown")
        metadata["status"] = status
        self.registry.update(batch_id, status=status, output_file_id=batch.get("output_file_id"))

        if status != "completed" or not batch.get("output_file_id"):
            LOGGER.warning("Batch did not complete successfully, falling back")
            return fallback_results, metadata

        # Build lookup for data merging
        entry_by_symbol = {e.profile.symbol.upper(): e for e in inputs}
        parsed: dict[str, TickerAnalysis] = {}
        try:
            output_lines = manager.download_output_lines(str(batch["output_file_id"]))
            for line in output_lines:
                custom_id = line.get("custom_id", "")
                symbol = custom_id.split(":")[-1].upper() if ":" in custom_id else custom_id.upper()
                if not symbol:
                    continue

                try:
                    content = extract_message_content(line)
                    payload = parse_json_from_model_output(content)
                    llm_model = TickerAnalysisLLM.model_validate(payload)
                    full_symbol = llm_model.ticker.upper() or symbol
                    entry = entry_by_symbol.get(full_symbol) or entry_by_symbol.get(symbol)
                    if entry:
                        parsed[full_symbol] = self._merge_pipeline_data(llm_model, entry)
                    else:
                        # No entry found; store with empty pipeline data
                        parsed[full_symbol] = TickerAnalysis(**llm_model.model_dump())
                except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                    LOGGER.warning("Invalid model output for %s: %s", symbol, exc)
        except Exception as exc:
            LOGGER.warning("OpenAI batch output download failed, falling back: %s", exc)
            metadata["status"] = "output_download_failed"
            metadata["error"] = str(exc)
            self.registry.update(batch_id, status="output_download_failed", error=str(exc))
            return fallback_results, metadata

        fallback_results.update(parsed)
        self.registry.update(batch_id, downloaded=True, downloaded_at=utc_now_iso(), parsed_items=len(parsed))
        return fallback_results, metadata

    def run(
        self,
        inputs: list[TickerLLMInput],
        run_date: str,
        artifacts_dir: Path,
        wait_for_batch: bool = False,
        on_ticker_done: object = None,
    ) -> tuple[dict[str, TickerAnalysis], dict]:
        if not inputs:
            return {}, {"mode": "empty"}

        fallback_results = self._fallback_map(inputs)

        if self.settings.dry_run or not self.settings.llm_live_mode:
            LOGGER.info("Using deterministic fallback analysis (dry-run or no LLM backend configured)")
            return fallback_results, {"mode": "fallback"}

        # Batch mode only works with the real OpenAI API; force direct mode for custom endpoints.
        use_direct = not self.settings.openai_use_batch or bool(self.settings.effective_llm_base_url)
        if use_direct:
            LOGGER.info("Using LLM direct mode")
            return self._run_direct(inputs=inputs, fallback_results=fallback_results, on_ticker_done=on_ticker_done)

        return self._run_batch(
            inputs=inputs,
            run_date=run_date,
            artifacts_dir=artifacts_dir,
            wait_for_batch=wait_for_batch,
            fallback_results=fallback_results,
        )


class WeeklyLLMEngine:
    """Optional weekly qualitative layer via OpenAI batch or direct endpoint."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = OpenAIBatchRegistry(settings.openai_batch_registry_path)

    @staticmethod
    def _compact_weekly_payload(deterministic_summary: dict) -> dict:
        """Extract only the highlights needed for LLM commentary.

        Sending all 99 ranking entries to the LLM is wasteful: the model would need to
        reproduce them in its output (hitting the token limit) and they carry no extra
        information for writing narrative commentary. We keep only the compact highlights.
        """
        return {
            "run_date": deterministic_summary.get("run_date"),
            "top_tickers": deterministic_summary.get("top_tickers", [])[:10],
            "worst_tickers": deterministic_summary.get("worst_tickers", [])[-10:],
            "recommended_basket": deterministic_summary.get("recommended_basket", []),
            "basket_rationale": deterministic_summary.get("basket_rationale", ""),
            "sector_clusters": deterministic_summary.get("sector_clusters", []),
            "competitive_relationships": deterministic_summary.get("competitive_relationships", []),
            "supply_chain_links": deterministic_summary.get("supply_chain_links", []),
            "scenario_signals": deterministic_summary.get("scenario_signals", []),
            "macro_themes": deterministic_summary.get("macro_themes", []),
            "watchlist": deterministic_summary.get("watchlist", []),
            "systemic_risks": deterministic_summary.get("systemic_risks", []),
        }

    def _generate_direct_commentary(
        self,
        run_date: str,
        deterministic_summary: dict,
    ) -> tuple[str | None, dict]:
        try:
            manager = OpenAIDirectManager(
                api_key=self.settings.effective_llm_api_key,
                base_url=self.settings.effective_llm_base_url,
                use_json_schema=self.settings.llm_use_json_schema,
            )
            compact_payload = self._compact_weekly_payload(deterministic_summary)
            request = BatchRequest(
                custom_id=f"{run_date}:weekly-summary",
                model=self.settings.effective_llm_model_weekly,
                system_prompt=build_weekly_system_prompt(),
                user_prompt=build_weekly_commentary_prompt(compact_payload),
                json_schema_name="weekly_commentary",
                json_schema=WeeklyLLMCommentary.model_json_schema(),
                max_completion_tokens=self.settings.openai_weekly_max_completion_tokens,
            )

            response_payload = manager.create_chat_completion(request)
            content = extract_chat_completion_content(response_payload)
            payload = parse_json_from_model_output(content)
            model = WeeklyLLMCommentary.model_validate(payload)
            status = "completed" if model.llm_commentary else "completed_no_commentary"
            return model.llm_commentary, {"mode": "openai_direct", "status": status}
        except Exception as exc:
            LOGGER.warning("Weekly direct commentary failed: %s", exc)
            return None, {"mode": "fallback", "reason": "weekly_direct_failed", "error": str(exc)}

    def generate_commentary(
        self,
        run_date: str,
        deterministic_summary: dict,
        artifacts_dir: Path,
        wait_for_batch: bool = True,
    ) -> tuple[str | None, dict]:
        if self.settings.dry_run or not self.settings.llm_live_mode:
            return None, {"mode": "skipped"}

        use_direct = not self.settings.openai_use_batch or bool(self.settings.effective_llm_base_url)
        if use_direct:
            return self._generate_direct_commentary(run_date=run_date, deterministic_summary=deterministic_summary)

        try:
            manager = OpenAIBatchManager(
                api_key=str(self.settings.effective_llm_api_key),
                completion_window=self.settings.openai_completion_window,
            )

            compact_payload = self._compact_weekly_payload(deterministic_summary)
            request = BatchRequest(
                custom_id=f"{run_date}:weekly-summary",
                model=self.settings.effective_llm_model_weekly,
                system_prompt=build_weekly_system_prompt(),
                user_prompt=build_weekly_commentary_prompt(compact_payload),
                json_schema_name="weekly_commentary",
                json_schema=WeeklyLLMCommentary.model_json_schema(),
                max_completion_tokens=self.settings.openai_weekly_max_completion_tokens,
            )

            jsonl_path = artifacts_dir / "weekly_summary_batch.jsonl"
            manager.write_requests_jsonl([request], jsonl_path)
            job = manager.submit_batch(
                jsonl_path,
                metadata={"pipeline": "weekly_summary", "run_date": run_date},
            )
        except Exception as exc:
            LOGGER.warning("Weekly commentary submission failed: %s", exc)
            return None, {"mode": "fallback", "reason": "weekly_batch_submission_failed", "error": str(exc)}

        batch_id = str(job.get("id"))
        initial_status = str(job.get("status") or "submitted")
        self.registry.upsert(
            {
                "batch_id": batch_id,
                "pipeline": "weekly_summary",
                "run_date": run_date,
                "status": initial_status,
                "completion_window": self.settings.openai_completion_window,
                "artifacts_dir": str(artifacts_dir),
                "submitted_at": utc_now_iso(),
                "downloaded": False,
            }
        )

        metadata = {
            "mode": "openai_batch",
            "batch_id": batch_id,
            "status": "submitted_pending" if not wait_for_batch else initial_status,
            "completion_window": self.settings.openai_completion_window,
        }

        if not wait_for_batch:
            self.registry.update(batch_id, status="submitted_pending")
            return None, metadata

        try:
            batch = manager.wait_for_completion(
                batch_id=batch_id,
                max_wait_minutes=self.settings.openai_max_wait_minutes,
                poll_seconds=self.settings.openai_poll_interval_seconds,
            )
        except Exception as exc:
            self.registry.update(batch_id, status="wait_failed", error=str(exc))
            return None, {**metadata, "status": "wait_failed", "error": str(exc)}

        status = str(batch.get("status") or "unknown")
        self.registry.update(batch_id, status=status, output_file_id=batch.get("output_file_id"))

        if status != "completed" or not batch.get("output_file_id"):
            return None, {**metadata, "status": status}

        try:
            lines = manager.download_output_lines(str(batch["output_file_id"]))
            if not lines:
                return None, {**metadata, "status": "completed_empty"}

            content = extract_message_content(lines[0])
            payload = parse_json_from_model_output(content)
            model = WeeklyLLMCommentary.model_validate(payload)
            self.registry.update(batch_id, downloaded=True, downloaded_at=utc_now_iso(), parsed_items=1)
            return model.llm_commentary, {**metadata, "status": "completed"}
        except Exception as exc:
            self.registry.update(batch_id, status="output_download_failed", error=str(exc))
            return None, {**metadata, "status": "output_download_failed", "error": str(exc)}


class MacroLLMEngine:
    """Generate macroeconomic analysis via OpenAI direct mode, with deterministic fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _compact_macro_payload(macro_context: dict) -> dict:
        """Extract the data the LLM needs to write its analysis."""
        indicators = macro_context.get("indicators", [])

        def _ind(symbol: str) -> dict | None:
            return next((i for i in indicators if i.get("symbol") == symbol), None)

        def _r(v, d=2):
            try:
                return round(float(v), d) if v is not None else None
            except (TypeError, ValueError):
                return None

        core_symbols = ["^VIX", "^GSPC", "^IXIC", "^RUT", "^TNX", "^IRX", "DX-Y.NYB", "GC=F", "CL=F", "TLT", "HYG"]
        core_inds = []
        for sym in core_symbols:
            ind = _ind(sym)
            if ind:
                core_inds.append({
                    "sym": sym,
                    "name": ind.get("name", ""),
                    "val": _r(ind.get("current_value")),
                    "1d": _r(ind.get("change_1d"), 4),
                    "1m": _r(ind.get("change_1m"), 4),
                    "3m": _r(ind.get("change_3m"), 4),
                })

        return {
            "run_date": macro_context.get("run_date"),
            "vix": _r(macro_context.get("vix_level")),
            "yield_curve_spread": _r(macro_context.get("yield_curve_spread"), 3),
            "indicators": core_inds,
            "sector_perf_1m": macro_context.get("sector_performance", {}),
        }

    @staticmethod
    def _deterministic_fallback(macro_context: dict) -> MacroAnalysis:
        """Build a rule-based macro analysis without calling OpenAI."""
        vix = macro_context.get("vix_level")
        spread = macro_context.get("yield_curve_spread")
        sector_perf = macro_context.get("sector_performance", {})

        # Regime from VIX
        if vix is None:
            macro_regime = "uncertain"
            vix_text = "VIX data unavailable."
        elif vix < 15:
            macro_regime = "risk-on"
            vix_text = f"VIX at {vix:.1f} signals low fear and a risk-on environment."
        elif vix < 25:
            macro_regime = "transitioning"
            vix_text = f"VIX at {vix:.1f} indicates moderate uncertainty; regime is transitioning."
        else:
            macro_regime = "risk-off"
            vix_text = f"VIX at {vix:.1f} signals elevated fear and a risk-off posture."

        # Yield curve
        if spread is None:
            yc_interp = "Yield curve data unavailable."
        elif spread < 0:
            yc_interp = f"Yield curve inverted ({spread:+.2f}pp): historically a recessionary signal."
        elif spread < 0.5:
            yc_interp = f"Yield curve flat ({spread:+.2f}pp): limited growth premium from longer maturities."
        else:
            yc_interp = f"Yield curve positive ({spread:+.2f}pp): normal term structure, supportive of growth."

        # Market breadth from sector performance
        if sector_perf:
            positive_sectors = sum(1 for v in sector_perf.values() if v > 0)
            total = len(sector_perf)
            ratio = positive_sectors / total if total else 0.5
            if ratio >= 0.7:
                breadth = "expanding"
            elif ratio >= 0.4:
                breadth = "mixed"
            else:
                breadth = "contracting"
        else:
            breadth = "mixed"

        # Sector rotation: best/worst
        if sector_perf:
            best = max(sector_perf, key=lambda k: sector_perf[k])
            worst = min(sector_perf, key=lambda k: sector_perf[k])
            rotation_signal = f"Leadership in {best} ({sector_perf[best]:+.1f}%); lagging in {worst} ({sector_perf[worst]:+.1f}%)."
        else:
            rotation_signal = "Sector rotation data unavailable."

        # Macro score: base 50, adjust for VIX and yield curve
        macro_score = 50.0
        if vix is not None:
            macro_score -= min(vix * 1.2, 30)
            macro_score += max(0, (20 - vix) * 0.5)
        if spread is not None and spread >= 0:
            macro_score += min(spread * 5, 15)
        if sector_perf:
            avg_perf = sum(sector_perf.values()) / len(sector_perf)
            macro_score += avg_perf * 0.5
        macro_score = max(0.0, min(100.0, round(macro_score, 2)))

        commentary = (
            f"{vix_text} "
            f"{yc_interp} "
            f"Sector breadth is {breadth}. {rotation_signal} "
            "This is a deterministic fallback analysis based on raw indicators — no LLM commentary available in dry-run mode."
        )

        return MacroAnalysis(
            run_date=macro_context.get("run_date", ""),
            macro_regime=macro_regime,
            market_breadth=breadth,
            key_macro_themes=[vix_text.rstrip("."), yc_interp.rstrip(".")],
            macro_risks=[
                "Elevated volatility" if (vix or 0) > 25 else "Monitor VIX for regime shift",
                "Inverted yield curve" if (spread or 1) < 0 else "Monitor credit spreads",
            ],
            sector_rotation_signal=rotation_signal,
            yield_curve_interpretation=yc_interp,
            dollar_impact="Dollar impact analysis unavailable in dry-run mode.",
            macro_commentary=commentary,
            macro_score=macro_score,
            indicators=macro_context.get("indicators", []),
            yield_curve_spread=spread,
            vix_level=vix,
            sector_performance=sector_perf,
        )

    def generate_analysis(
        self,
        run_date: str,
        macro_context: dict,
        artifacts_dir: Path,
    ) -> tuple[MacroAnalysis, dict]:
        """Generate macro analysis. Returns (MacroAnalysis, metadata_dict)."""
        if self.settings.dry_run or not self.settings.llm_live_mode:
            result = self._deterministic_fallback({**macro_context, "run_date": run_date})
            return result, {"mode": "fallback"}

        try:
            manager = OpenAIDirectManager(
                api_key=self.settings.effective_llm_api_key,
                base_url=self.settings.effective_llm_base_url,
                use_json_schema=self.settings.llm_use_json_schema,
            )
        except Exception as exc:
            LOGGER.warning("MacroLLMEngine: LLM init failed, using fallback: %s", exc)
            result = self._deterministic_fallback({**macro_context, "run_date": run_date})
            return result, {"mode": "fallback", "reason": "llm_init_failed", "error": str(exc)}

        schema = MacroAnalysisLLM.model_json_schema()
        compact_payload = self._compact_macro_payload(macro_context)
        request = BatchRequest(
            custom_id=f"{run_date}:macro-analysis",
            model=self.settings.effective_llm_model_weekly,
            system_prompt=build_macro_system_prompt(),
            user_prompt=build_macro_user_prompt(compact_payload),
            json_schema_name="macro_analysis",
            json_schema=schema,
            max_completion_tokens=self.settings.openai_weekly_max_completion_tokens,
        )

        try:
            response_payload = manager.create_chat_completion(request)
            content = extract_chat_completion_content(response_payload)
            payload = parse_json_from_model_output(content)
            llm_model = MacroAnalysisLLM.model_validate(payload)
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            LOGGER.warning("MacroLLMEngine: invalid model output: %s", exc)
            return (
                self._deterministic_fallback({**macro_context, "run_date": run_date}),
                {"mode": "fallback", "reason": "invalid_model_output", "error": str(exc)},
            )
        except Exception as exc:
            LOGGER.warning("MacroLLMEngine: request failed: %s", exc)
            return (
                self._deterministic_fallback({**macro_context, "run_date": run_date}),
                {"mode": "fallback", "reason": "request_failed", "error": str(exc)},
            )

        # Merge LLM output with raw indicator data
        result = MacroAnalysis(
            run_date=run_date,
            macro_regime=llm_model.macro_regime,
            market_breadth=llm_model.market_breadth,
            key_macro_themes=llm_model.key_macro_themes,
            macro_risks=llm_model.macro_risks,
            sector_rotation_signal=llm_model.sector_rotation_signal,
            yield_curve_interpretation=llm_model.yield_curve_interpretation,
            dollar_impact=llm_model.dollar_impact,
            macro_commentary=llm_model.macro_commentary,
            macro_score=llm_model.macro_score,
            indicators=macro_context.get("indicators", []),
            yield_curve_spread=macro_context.get("yield_curve_spread"),
            vix_level=macro_context.get("vix_level"),
            sector_performance=macro_context.get("sector_performance", {}),
        )
        return result, {"mode": "openai_direct", "status": "completed"}
