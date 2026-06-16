"""Tests for webhook listener helpers."""

from __future__ import annotations

import hmac
from hashlib import sha256
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.webhook_service import WebhookService


def test_signature_validation_with_secret() -> None:
    service = WebhookService(
        host="127.0.0.1",
        port=8765,
        callback=lambda _event, _payload: None,
        secret="secret",
    )
    body = b'{"ok":true}'
    digest = hmac.new(b"secret", body, sha256).hexdigest()

    request = Mock()
    request.headers = {"X-Hub-Signature-256": f"sha256={digest}"}

    assert service._is_valid_signature(request, body)  # noqa: SLF001


def test_signature_validation_without_secret() -> None:
    service = WebhookService(
        host="127.0.0.1",
        port=8765,
        callback=lambda _event, _payload: None,
        secret=None,
    )
    request = Mock()
    request.headers = {}

    assert service._is_valid_signature(request, b"body")  # noqa: SLF001


def test_start_and_stop_lifecycle() -> None:
    service = WebhookService("127.0.0.1", 8765, callback=lambda _e, _p: None, secret=None)
    fake_thread = Mock()
    fake_thread.is_alive.return_value = False

    with patch("src.services.webhook_service.threading.Thread", return_value=fake_thread):
        service.start()

    service._loop = Mock()  # noqa: SLF001
    service._thread = Mock()  # noqa: SLF001
    service._thread.is_alive.return_value = True  # type: ignore[attr-defined]  # noqa: SLF001
    service.stop()
    service._loop.call_soon_threadsafe.assert_called_once()  # type: ignore[attr-defined]  # noqa: SLF001
    service._thread.join.assert_called_once()  # type: ignore[attr-defined]  # noqa: SLF001


@pytest.mark.asyncio
async def test_handle_webhook_invalid_signature() -> None:
    service = WebhookService("127.0.0.1", 8765, callback=lambda _e, _p: None, secret="secret")
    request = Mock()
    request.read = AsyncMock(return_value=b"{}")
    request.headers = {"X-Hub-Signature-256": "sha256=bad", "X-GitHub-Event": "pull_request"}

    response = await service._handle_webhook(request)  # noqa: SLF001
    assert response.status == 401


@pytest.mark.asyncio
async def test_handle_webhook_valid_signature_and_payload() -> None:
    captured: list[tuple[str, dict]] = []
    service = WebhookService(
        "127.0.0.1",
        8765,
        callback=lambda event, payload: captured.append((event, payload)),
        secret="secret",
    )
    body = b'{"action":"opened"}'
    digest = hmac.new(b"secret", body, sha256).hexdigest()
    request = Mock()
    request.read = AsyncMock(return_value=body)
    request.headers = {
        "X-Hub-Signature-256": f"sha256={digest}",
        "X-GitHub-Event": "pull_request",
    }

    response = await service._handle_webhook(request)  # noqa: SLF001
    assert response.status == 200
    assert captured == [("pull_request", {"action": "opened"})]


@pytest.mark.asyncio
async def test_handle_webhook_empty_body() -> None:
    captured: list[tuple[str, dict]] = []
    service = WebhookService(
        "127.0.0.1",
        8765,
        callback=lambda event, payload: captured.append((event, payload)),
        secret=None,
    )
    request = Mock()
    request.read = AsyncMock(return_value=b"")
    request.headers = {"X-GitHub-Event": "ping"}

    response = await service._handle_webhook(request)  # noqa: SLF001
    assert response.status == 200
    assert captured == [("ping", {})]


def test_run_server_cleanup_path() -> None:
    service = WebhookService("127.0.0.1", 8765, callback=lambda _e, _p: None, secret=None)

    loop = Mock()
    loop.run_until_complete = Mock()
    loop.run_forever = Mock(side_effect=RuntimeError("boom"))
    loop.close = Mock()

    runner = Mock()
    runner.setup = Mock(return_value=None)
    runner.cleanup = Mock(return_value=None)

    with (
        patch("src.services.webhook_service.asyncio.new_event_loop", return_value=loop),
        patch("src.services.webhook_service.asyncio.set_event_loop"),
        patch("src.services.webhook_service.web.AppRunner", return_value=runner),
        patch("src.services.webhook_service.web.TCPSite") as mock_site,
    ):
        mock_site.return_value.start = Mock(return_value=None)
        with pytest.raises(RuntimeError):
            service._run_server()  # noqa: SLF001

    assert loop.close.called
