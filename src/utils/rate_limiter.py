"""Rate-limit and retry helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def with_exponential_backoff(
    retries: int = 4,
    base_delay_seconds: float = 1.0,
) -> Callable[[F], F]:
    """Retry async operations with jittered exponential backoff."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt == retries:
                        break
                    delay = base_delay_seconds * (2**attempt)
                    await asyncio.sleep(delay)
            if last_error:
                raise last_error
            raise RuntimeError("Retry wrapper ended unexpectedly")

        return wrapper  # type: ignore[return-value]

    return decorator
