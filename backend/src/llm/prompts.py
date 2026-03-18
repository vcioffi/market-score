from __future__ import annotations

import json


def build_ticker_system_prompt() -> str:
    return (
        "You are a senior equity analyst following Benjamin Graham's value investing framework. "
        "Return only valid JSON matching the provided schema. "
        "No markdown, no commentary, no extra keys. "
        "Use concise professional language and calibrated scores from 0 to 100. "
        "Do NOT include price_history, quant_metrics, or fundamentals in your output — "
        "those fields are injected by the pipeline from stored market data. "
        "For the fundamental_analysis field apply a top-down approach: assess the company's "
        "economic moat, management quality, and growth prospects, then evaluate financial health "
        "(balance sheet, cash flow, leverage) and finally produce a Graham-style fair value verdict "
        "(undervalued/fairly_valued/overvalued) referencing P/E, P/B, Graham Number, and margin of safety "
        "when the data is available."
    )


def build_ticker_user_prompt(payload: dict) -> str:
    return (
        "Analyze this ticker and output one JSON object. "
        "Be concise and calibrated. Include actionable monitoring triggers. "
        "Fill the fundamental_analysis object with a rigorous Graham-style assessment.\n"
        + json.dumps(payload, separators=(",", ":"))
    )


def build_weekly_system_prompt() -> str:
    return (
        "You are a portfolio strategist. Return only valid JSON matching the schema. "
        "Use risk aware language and avoid unsupported claims."
    )


def build_weekly_user_prompt(payload: dict) -> str:
    return (
        "Create the weekly cross-ticker summary from the input. "
        "Preserve ranking consistency and produce realistic basket weights.\n"
        + json.dumps(payload, separators=(",", ":"))
    )


def build_macro_system_prompt() -> str:
    return (
        "You are a senior macro strategist. Return only valid JSON matching the provided schema. "
        "No markdown, no commentary, no extra keys. "
        "Interpret the macroeconomic indicators provided and produce a concise, calibrated analysis. "
        "Use professional financial language. Scores must be 0-100."
    )


def build_macro_user_prompt(payload: dict) -> str:
    return (
        "Analyze the following macroeconomic indicators and output one JSON object. "
        "Write a macro_commentary of 3-5 paragraphs covering: market regime, yield curve dynamics, "
        "sector rotation, currency and commodity signals, key risks and outlook. "
        "Write the macro_commentary in Italian.\n"
        + json.dumps(payload, separators=(",", ":"))
    )


def build_weekly_commentary_prompt(compact_payload: dict) -> str:
    """Build a compact prompt for weekly narrative commentary only.

    The input is a trimmed summary (top/worst tickers, basket, sector clusters,
    macro themes, risks) — NOT the full 99-ticker ranking which would blow
    the output token budget. The LLM only generates llm_commentary.
    """
    return (
        "You are a portfolio strategist. Write a concise weekly commentary (3-5 paragraphs) "
        "covering: market leadership, sector dynamics, key risks, and actionable outlook. "
        "Base it strictly on the data below. Return only JSON: "
        '{"llm_commentary": "your text here"}\n'
        + json.dumps(compact_payload, separators=(",", ":"))
    )
