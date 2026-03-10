from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from src.llm.fallback import parse_json_from_model_output
from src.news.models import NewsArticle, NewsContext
from src.tickers.models import TickerProfile
from src.utils.logging import get_logger
from src.utils.retry import with_retry

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - handled at runtime
    OpenAI = None  # type: ignore

LOGGER = get_logger(__name__)


class OpenAINewsResearchService:
    """Use OpenAI web search tool to build ticker and sector news context."""

    def __init__(
        self,
        api_key: str,
        model: str,
        search_context_size: str = "high",
        max_output_tokens: int = 2600,
    ):
        if OpenAI is None:
            raise RuntimeError(
                "openai package is required for OpenAI web research mode. Install dependencies with: pip install -r requirements.txt"
            )
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.search_context_size = search_context_size
        self.max_output_tokens = max_output_tokens

    def _truncate_summary(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].strip() + "..."

    def _normalize_domain(self, value: str) -> str:
        raw = value.strip()
        if not raw:
            return ""

        candidate = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(candidate)
        host = parsed.netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or raw.lower()

    def _extract_response_sources(self, response_payload: dict[str, Any]) -> list[str]:
        output = response_payload.get("output")
        if not isinstance(output, list):
            return []

        domains: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "web_search_call":
                continue
            action = item.get("action")
            if not isinstance(action, dict):
                continue
            sources = action.get("sources")
            if not isinstance(sources, list):
                continue

            for source in sources:
                if not isinstance(source, dict):
                    continue
                raw_url = source.get("url") or source.get("site")
                if not raw_url:
                    continue
                domain = self._normalize_domain(str(raw_url))
                if domain and domain not in domains:
                    domains.append(domain)

        return domains

    def _dedupe(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        seen: set[tuple[str, str]] = set()
        output: list[NewsArticle] = []
        for article in articles:
            key = (article.title.strip().lower(), article.url.strip())
            if key in seen:
                continue
            seen.add(key)
            output.append(article)
        return output

    def _limit_window(self, articles: list[NewsArticle], window_days: int) -> list[NewsArticle]:
        threshold = datetime.now(timezone.utc) - timedelta(days=window_days)
        limited = []
        for item in articles:
            if item.published_at is None:
                limited.append(item)
                continue
            # Normalise to UTC-aware so comparison never throws offset-naive errors
            pub = item.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub >= threshold:
                limited.append(item)
        return limited

    def _normalize_articles(
        self,
        raw_items: list[dict[str, Any]],
        category: str,
        related_symbol: str,
        max_items: int,
        summary_char_limit: int,
        window_days: int,
    ) -> list[NewsArticle]:
        items: list[NewsArticle] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip()
            url = str(raw.get("url") or "").strip()
            if not title or not url:
                continue

            payload = {
                "title": title,
                "url": url,
                "source": str(raw.get("source") or "web"),
                "published_at": raw.get("published_at"),
                "summary": self._truncate_summary(str(raw.get("summary") or "").strip(), summary_char_limit),
                "related_symbol": str(raw.get("related_symbol") or related_symbol).upper(),
                "category": category,
            }

            try:
                items.append(NewsArticle.model_validate(payload))
            except Exception:
                continue

        items = self._dedupe(items)
        items = self._limit_window(items, window_days)
        return items[:max_items]

    def _build_prompt(
        self,
        profile: TickerProfile,
        max_company_news: int,
        max_sector_news: int,
        window_days: int,
        summary_char_limit: int,
    ) -> str:
        peers = ", ".join(profile.peers[:4]) if profile.peers else "none"
        # Cap summary chars in prompt to keep output compact
        capped_summary = min(summary_char_limit, 280)
        return (
            "You are a financial research analyst. "
            "Search the web for recent news and return ONLY a compact JSON object. "
            "Be brief. No markdown. No prose outside JSON.\n\n"
            f"Company: {profile.company_name} ({profile.symbol}) | "
            f"Sector: {profile.sector} | Peers: {peers}\n"
            f"Window: last {window_days} days | "
            f"Max company articles: {max_company_news} | "
            f"Max sector articles: {max_sector_news} | "
            f"Summary max: {capped_summary} chars each\n\n"
            "Return this JSON (nothing else):\n"
            "{\n"
            '  "company_news": [{"title":"...","url":"https://...","source":"...","published_at":"ISO or null","summary":"...","related_symbol":"SYM","category":"company"}],\n'
            '  "sector_news": [{"title":"...","url":"https://...","source":"...","published_at":"ISO or null","summary":"...","related_symbol":"SYM","category":"sector"}],\n'
            '  "sources_used": ["openai_web_search"],\n'
            '  "company_sentiment": {"score_0_100": 50, "label": "neutral", "rationale": "..."},\n'
            '  "sector_sentiment": {"score_0_100": 50, "label": "neutral", "rationale": "..."}\n'
            "}"
        )

    def _is_deep_research_model(self) -> bool:
        return "deep-research" in self.model

    def _web_search_tool_type(self) -> str:
        if self._is_deep_research_model():
            return "web_search_preview"
        return "web_search"

    def _effective_search_context_size(self) -> str:
        # deep-research models only support 'medium' context size
        if self._is_deep_research_model():
            return "medium"
        return self.search_context_size

    def _extract_text_from_output(self, response_payload: dict) -> str:
        """Extract text content from response output items, falling back to output_text."""
        output = response_payload.get("output")
        if isinstance(output, list):
            parts: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                # message item contains text content
                if item_type == "message":
                    content = item.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "output_text":
                                parts.append(str(block.get("text") or ""))
                    elif isinstance(content, str):
                        parts.append(content)
                # reasoning or text items
                elif item_type in ("text", "output_text"):
                    parts.append(str(item.get("text") or ""))
            if parts:
                return "".join(parts)
        return ""

    @with_retry(attempts=2, min_wait_seconds=1.0, max_wait_seconds=6.0)
    def _research(self, prompt: str) -> tuple[str, list[str]]:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            max_output_tokens=self.max_output_tokens,
            include=["web_search_call.action.sources"],
            tools=[
                {
                    "type": self._web_search_tool_type(),
                    "search_context_size": self._effective_search_context_size(),
                }
            ],
        )
        response_status = getattr(response, "status", None)
        if response_status and response_status not in ("completed", "succeeded"):
            # Raise RuntimeError (not ValueError) so tenacity does NOT retry:
            # retrying with identical settings will just waste money on the same result.
            raise RuntimeError(
                f"OpenAI Responses API returned incomplete status: {response_status!r}. "
                "Try increasing max_output_tokens or reducing the prompt length."
            )
        response_payload = response.model_dump()
        # output_text may be None when response only contains web_search_call items;
        # fall back to manual extraction from output list
        output_text = response.output_text or self._extract_text_from_output(response_payload)
        if not output_text or not output_text.strip():
            raise RuntimeError(
                "OpenAI Responses API returned empty text output. "
                "The model may have only returned search results without a text response."
            )
        response_sources = self._extract_response_sources(response_payload)
        return output_text, response_sources

    def build_context(
        self,
        profile: TickerProfile,
        max_company_news: int,
        max_sector_news: int,
        window_days: int,
        summary_char_limit: int,
    ) -> NewsContext:
        prompt = self._build_prompt(
            profile=profile,
            max_company_news=max_company_news,
            max_sector_news=max_sector_news,
            window_days=window_days,
            summary_char_limit=summary_char_limit,
        )

        raw_text, response_sources = self._research(prompt)
        payload = parse_json_from_model_output(raw_text)

        company_news = self._normalize_articles(
            raw_items=payload.get("company_news") or [],
            category="company",
            related_symbol=profile.symbol,
            max_items=max_company_news,
            summary_char_limit=summary_char_limit,
            window_days=window_days,
        )
        sector_news = self._normalize_articles(
            raw_items=payload.get("sector_news") or [],
            category="sector",
            related_symbol=profile.symbol,
            max_items=max_sector_news,
            summary_char_limit=summary_char_limit,
            window_days=window_days,
        )

        sources_used = payload.get("sources_used") or []
        if not isinstance(sources_used, list):
            sources_used = []
        sources = [str(item) for item in sources_used if str(item).strip()]
        for source in response_sources:
            if source not in sources:
                sources.append(source)
        if "openai_web_search" not in sources:
            sources.insert(0, "openai_web_search")

        context_payload: dict[str, Any] = {
            "company_news": [item.model_dump(mode="json") for item in company_news],
            "sector_news": [item.model_dump(mode="json") for item in sector_news],
            "sources_used": sources,
        }

        company_sentiment = payload.get("company_sentiment")
        sector_sentiment = payload.get("sector_sentiment")
        if isinstance(company_sentiment, dict):
            context_payload["company_sentiment"] = company_sentiment
        if isinstance(sector_sentiment, dict):
            context_payload["sector_sentiment"] = sector_sentiment

        context = NewsContext.model_validate(context_payload)
        LOGGER.debug(
            "OpenAI news context for %s -> %d company, %d sector",
            profile.symbol,
            len(context.company_news),
            len(context.sector_news),
        )
        return context
