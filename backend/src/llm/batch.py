from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger
from src.utils.retry import with_retry

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - handled at runtime
    OpenAI = None  # type: ignore

LOGGER = get_logger(__name__)


@dataclass
class BatchRequest:
    custom_id: str
    model: str
    system_prompt: str
    user_prompt: str
    json_schema_name: str
    json_schema: dict[str, Any]
    max_completion_tokens: int | None = None
    temperature: float | None = None


def normalize_openai_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize JSON schema to satisfy OpenAI strict json_schema requirements."""

    normalized = deepcopy(schema)

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            is_object = node.get("type") == "object" or "properties" in node
            if is_object:
                properties = node.get("properties") if isinstance(node.get("properties"), dict) else {}
                # OpenAI strict json_schema requires explicit additionalProperties=false
                # and required must include every key in properties.
                node["additionalProperties"] = False
                node["required"] = list(properties.keys())
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(normalized)
    return normalized

def _build_response_format(request: BatchRequest) -> dict[str, Any]:
    if request.json_schema:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": request.json_schema_name,
                "schema": normalize_openai_json_schema(request.json_schema),
                "strict": True,
            },
        }
    return {"type": "json_object"}


class OpenAIBatchManager:
    """Build, submit and retrieve OpenAI batch jobs with 24h completion windows."""

    def __init__(self, api_key: str, completion_window: str = "24h"):
        if OpenAI is None:
            raise RuntimeError(
                "openai package is required for live batch mode. Install dependencies with: pip install -r requirements.txt"
            )
        self.client = OpenAI(api_key=api_key)
        self.completion_window = completion_window

    def write_requests_jsonl(self, requests: list[BatchRequest], target_path: Path) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("w", encoding="utf-8") as handle:
            for request in requests:
                body = {
                    "model": request.model,
                    "messages": [
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": request.user_prompt},
                    ],
                    "response_format": _build_response_format(request),
                }
                if request.max_completion_tokens is not None:
                    body["max_completion_tokens"] = request.max_completion_tokens
                if request.temperature is not None:
                    body["temperature"] = request.temperature

                row = {
                    "custom_id": request.custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": body,
                }
                handle.write(json.dumps(row) + "\n")
        return target_path

    def submit_batch(self, jsonl_path: Path, metadata: dict[str, str] | None = None) -> dict:
        with jsonl_path.open("rb") as file_handle:
            uploaded = self.client.files.create(file=file_handle, purpose="batch")
        batch = self.client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/chat/completions",
            completion_window=self.completion_window,
            metadata=metadata or {},
        )
        LOGGER.info("OpenAI batch submitted: %s", batch.id)
        return batch.model_dump()

    def get_batch(self, batch_id: str) -> dict:
        batch = self.client.batches.retrieve(batch_id)
        return batch.model_dump()

    def wait_for_completion(self, batch_id: str, max_wait_minutes: int, poll_seconds: int) -> dict:
        max_seconds = max_wait_minutes * 60
        elapsed = 0
        while elapsed <= max_seconds:
            batch = self.get_batch(batch_id)
            status = batch.get("status")
            if status in {"completed", "failed", "expired", "cancelled"}:
                return batch
            time.sleep(poll_seconds)
            elapsed += poll_seconds
        raise TimeoutError(f"Batch {batch_id} did not complete within {max_wait_minutes} minutes")

    def download_output_lines(self, output_file_id: str) -> list[dict]:
        content = self.client.files.content(output_file_id)
        text = content.text
        lines = [line for line in text.splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    def download_file_text(self, file_id: str) -> str:
        content = self.client.files.content(file_id)
        return content.text


class OpenAIDirectManager:
    """Run synchronous chat completions against any OpenAI-compatible endpoint."""

    def __init__(self, api_key: str | None, base_url: str | None = None, use_json_schema: bool = True):
        if OpenAI is None:
            raise RuntimeError(
                "openai package is required for live direct mode. Install dependencies with: pip install -r requirements.txt"
            )
        # For local endpoints (e.g. Ollama) an API key is not required; use a placeholder.
        effective_key = api_key or "local"
        self.client = OpenAI(api_key=effective_key, base_url=base_url) if base_url else OpenAI(api_key=effective_key)
        self.use_json_schema = use_json_schema

    @with_retry(attempts=3, min_wait_seconds=1.0, max_wait_seconds=8.0)
    def create_chat_completion(self, request: BatchRequest) -> dict:
        # Use json_schema strict mode only when the provider supports it (OpenAI, Groq, etc.).
        # Fall back to json_object for providers that don't support strict schema (Ollama).
        if self.use_json_schema:
            response_format = _build_response_format(request)
        else:
            response_format = {"type": "json_object"}
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "response_format": response_format,
        }
        if request.max_completion_tokens is not None:
            body["max_completion_tokens"] = request.max_completion_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature

        response = self.client.chat.completions.create(**body)
        return response.model_dump()


def extract_message_content(batch_output_line: dict) -> str:
    response = batch_output_line.get("response", {})
    body = response.get("body", {})
    choices = body.get("choices", [])
    if not choices:
        raise ValueError("Batch output has no completion choices")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        parts = []
        for entry in content:
            if isinstance(entry, dict):
                parts.append(entry.get("text", ""))
            else:
                parts.append(str(entry))
        return "".join(parts)
    return str(content)


def extract_chat_completion_content(response_payload: dict) -> str:
    choices = response_payload.get("choices", [])
    if not choices:
        raise ValueError("Chat completion has no completion choices")
    choice = choices[0]
    finish_reason = choice.get("finish_reason")
    message = choice.get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        parts = []
        for entry in content:
            if isinstance(entry, dict):
                parts.append(entry.get("text", ""))
            else:
                parts.append(str(entry))
        content = "".join(parts)
    else:
        content = str(content) if content is not None else ""
    if not content.strip():
        raise ValueError(
            f"Chat completion returned empty content (finish_reason={finish_reason!r}). "
            "The model may have hit max_completion_tokens or returned a refusal."
        )
    return content
