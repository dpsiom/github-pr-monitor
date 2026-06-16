"""Tests for retry helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.utils.rate_limiter import with_exponential_backoff


@pytest.mark.asyncio
async def test_retry_eventually_succeeds() -> None:
    counter = {"n": 0}

    @with_exponential_backoff(retries=2, base_delay_seconds=0.001)
    async def flaky() -> str:
        counter["n"] += 1
        if counter["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    result = await flaky()
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_raises_last_error_after_exhaustion() -> None:
    counter = {"n": 0}

    @with_exponential_backoff(retries=2, base_delay_seconds=0.001)
    async def always_fails() -> None:
        counter["n"] += 1
        raise RuntimeError("still failing")

    with pytest.raises(RuntimeError, match="still failing"):
        await always_fails()

    assert counter["n"] == 3


@pytest.mark.asyncio
async def test_retry_uses_exponential_delays() -> None:
    counter = {"n": 0}
    sleep_mock = AsyncMock()

    @with_exponential_backoff(retries=3, base_delay_seconds=0.5)
    async def flaky() -> str:
        counter["n"] += 1
        if counter["n"] < 4:
            raise ValueError("transient")
        return "ok"

    with patch("src.utils.rate_limiter.asyncio.sleep", sleep_mock):
        result = await flaky()

    assert result == "ok"
    assert sleep_mock.await_args_list == [
        ((0.5,), {}),
        ((1.0,), {}),
        ((2.0,), {}),
    ]


@pytest.mark.asyncio
async def test_zero_retries_does_not_sleep() -> None:
    sleep_mock = AsyncMock()

    @with_exponential_backoff(retries=0, base_delay_seconds=1.0)
    async def fails_once() -> None:
        raise RuntimeError("no retry")

    with (
        patch("src.utils.rate_limiter.asyncio.sleep", sleep_mock),
        pytest.raises(RuntimeError, match="no retry"),
    ):
        await fails_once()

    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_negative_retries_hits_defensive_runtime_error() -> None:
    @with_exponential_backoff(retries=-1, base_delay_seconds=1.0)
    async def never_called() -> str:
        return "ok"

    with pytest.raises(RuntimeError, match="Retry wrapper ended unexpectedly"):
        await never_called()
