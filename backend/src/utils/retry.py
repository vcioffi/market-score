from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

F = TypeVar("F", bound=Callable[..., object])


def _should_retry(exception: BaseException) -> bool:
    """Retry transient errors, but skip permanent configuration/request issues."""

    if isinstance(exception, RuntimeError):
        return False

    status_code = getattr(exception, "status_code", None)
    if isinstance(status_code, int):
        if status_code in {408, 409, 429}:
            return True
        if 400 <= status_code < 500:
            return False

    return True


def with_retry(attempts: int = 3, min_wait_seconds: float = 1.0, max_wait_seconds: float = 6.0):
    """Retry decorator with bounded exponential backoff."""

    return retry(
        reraise=True,
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_seconds, max=max_wait_seconds),
        retry=retry_if_exception(_should_retry),
    )
