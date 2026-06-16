"""Tests for PR service orchestration and action routing."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.api.models import CIStatus, PRFileSummary, PullRequest
from src.config.settings import AppConfig, AppSettings
from src.services.pr_service import PRService


def _sample_pr() -> PullRequest:
    return PullRequest(
        repo="octo/repo",
        number=1,
        title="Test PR",
        author="octocat",
        state="OPEN",
        base_branch="main",
        head_branch="feature",
        html_url="https://github.com/octo/repo/pull/1",
        updated_at=datetime.now(),
        files=PRFileSummary(),
        ci_status=CIStatus(state="SUCCESS"),
    )


@pytest.mark.asyncio
async def test_refresh_once_publishes_results() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    published: list[tuple[str, object]] = []
    service.notification_service.subscribe(
        "prs_updated",
        lambda name, payload: published.append((name, payload)),
    )
    service.gateway = SimpleNamespace(  # type: ignore[assignment]
        fetch_pending_review_prs=AsyncMock(return_value=[_sample_pr()]),
    )

    await service._refresh_once()  # noqa: SLF001

    assert published


def test_on_webhook_event_triggers_refresh() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    called = {"refresh": 0}

    def _refresh() -> None:
        called["refresh"] += 1

    service.force_refresh = _refresh  # type: ignore[method-assign]
    service._on_webhook_event("pull_request", {"action": "opened"})  # noqa: SLF001
    service._on_webhook_event("ping", {"zen": "ok"})  # noqa: SLF001

    assert called["refresh"] == 1


def test_start_and_stop_manage_webhook_listener() -> None:
    config = AppConfig()
    config.monitor.realtime_mode = "webhook"
    service = PRService(settings=AppSettings(config=config), token="token")

    fake_thread = Mock()
    fake_thread.is_alive.return_value = False

    with (
        patch("src.services.pr_service.WebhookService") as mock_webhook_cls,
        patch("src.services.pr_service.threading.Thread", return_value=fake_thread),
    ):
        service.start()
        service.stop()

    mock_webhook_cls.assert_called_once()


def test_subscribe_updates_and_errors_callbacks() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    pr = _sample_pr()
    updated: list[tuple[list[PullRequest], datetime]] = []
    errors: list[str] = []

    service.subscribe_updates(lambda prs, ts: updated.append((prs, ts)))
    service.subscribe_error(lambda message: errors.append(message))

    now = datetime.now()
    service.notification_service.publish("prs_updated", {"prs": [pr], "ts": now})
    service.notification_service.publish("polling_error", "boom")

    assert updated and updated[0][0][0].number == 1
    assert errors == ["boom"]


def test_start_returns_when_thread_already_running() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    running_thread = Mock()
    running_thread.is_alive.return_value = True
    service._thread = running_thread  # noqa: SLF001

    with patch("src.services.pr_service.threading.Thread") as mock_thread:
        service.start()

    mock_thread.assert_not_called()


def test_stop_joins_running_thread_without_webhook() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    thread = Mock()
    thread.is_alive.return_value = True
    service._thread = thread  # noqa: SLF001

    service.stop()

    thread.join.assert_called_once_with(timeout=2)


def test_run_loop_invokes_asyncio_run() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")

    def _fake_run(coro: object) -> None:
        coro.close()  # type: ignore[attr-defined]

    with patch("src.services.pr_service.asyncio.run", side_effect=_fake_run) as mock_run:
        service._run_loop()  # noqa: SLF001

    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_polling_loop_handles_exception_and_sleeps() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    errors: list[str] = []
    service.subscribe_error(lambda message: errors.append(message))

    call_count = {"n": 0}

    async def _boom() -> None:
        call_count["n"] += 1
        raise RuntimeError("loop-fail")

    async def _sleep(_seconds: int) -> None:
        service._stop_event.set()  # noqa: SLF001

    service._refresh_once = _boom  # type: ignore[method-assign]  # noqa: SLF001
    with patch("src.services.pr_service.asyncio.sleep", side_effect=_sleep):
        await service._polling_loop()  # noqa: SLF001

    assert call_count["n"] == 1
    assert errors and "loop-fail" in errors[0]


def test_force_refresh_returns_when_lock_unavailable() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    service._refresh_lock = Mock()  # noqa: SLF001
    service._refresh_lock.acquire.return_value = False  # type: ignore[attr-defined]  # noqa: SLF001

    with patch("src.services.pr_service.asyncio.run") as mock_run:
        service.force_refresh()

    mock_run.assert_not_called()


def test_force_refresh_publishes_error_on_exception() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    errors: list[str] = []
    service.subscribe_error(lambda message: errors.append(message))

    async def _boom() -> None:
        raise RuntimeError("fail")

    service._refresh_once = _boom  # type: ignore[method-assign]  # noqa: SLF001
    service.force_refresh()

    assert errors and "fail" in errors[0]


def test_get_pull_request_details_passthrough() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    pr = _sample_pr()
    service.gateway = SimpleNamespace(fetch_pull_request_details=AsyncMock(return_value=pr))  # type: ignore[assignment]

    detailed = service.get_pull_request_details(pr)
    assert detailed is pr


def test_run_action_wraps_async_executor() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")

    def _fake_run(coro: object) -> None:
        coro.close()  # type: ignore[attr-defined]

    with patch("src.services.pr_service.asyncio.run", side_effect=_fake_run) as mock_run:
        service.run_action("approve", _sample_pr(), comment="ok")

    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_action_validations_raise_errors() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    service.gateway = SimpleNamespace(  # type: ignore[assignment]
        approve=AsyncMock(),
        request_changes=AsyncMock(),
        comment=AsyncMock(),
        merge=AsyncMock(),
        close_with_comment=AsyncMock(),
        add_line_comment=AsyncMock(),
    )

    with pytest.raises(ValueError):
        await service._run_action_async(  # noqa: SLF001
            action="request_changes",
            pr=_sample_pr(),
            comment=None,
            merge_method="merge",
            line_path=None,
            line_number=None,
        )

    with pytest.raises(ValueError):
        await service._run_action_async(  # noqa: SLF001
            action="line_comment",
            pr=_sample_pr(),
            comment=None,
            merge_method="merge",
            line_path="src/main.py",
            line_number=1,
        )

    with pytest.raises(ValueError):
        await service._run_action_async(  # noqa: SLF001
            action="line_comment",
            pr=_sample_pr(),
            comment="body",
            merge_method="merge",
            line_path="src/main.py",
            line_number=None,
        )

    with pytest.raises(ValueError):
        await service._run_action_async(  # noqa: SLF001
            action="comment",
            pr=_sample_pr(),
            comment=None,
            merge_method="merge",
            line_path=None,
            line_number=None,
        )

    with pytest.raises(ValueError):
        await service._run_action_async(  # noqa: SLF001
            action="unknown",
            pr=_sample_pr(),
            comment="x",
            merge_method="merge",
            line_path=None,
            line_number=None,
        )


@pytest.mark.asyncio
async def test_run_action_routes_line_comment() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    service.gateway = SimpleNamespace(  # type: ignore[assignment]
        approve=AsyncMock(),
        request_changes=AsyncMock(),
        comment=AsyncMock(),
        merge=AsyncMock(),
        close_with_comment=AsyncMock(),
        add_line_comment=AsyncMock(),
    )

    await service._run_action_async(  # noqa: SLF001
        action="line_comment",
        pr=_sample_pr(),
        comment="Please rename this var",
        merge_method="merge",
        line_path="src/main.py",
        line_number=12,
    )

    service.gateway.add_line_comment.assert_awaited_once_with(  # type: ignore[attr-defined]
        "octo/repo",
        1,
        "Please rename this var",
        "src/main.py",
        12,
    )


@pytest.mark.asyncio
async def test_run_action_rejects_missing_line_data() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    service.gateway = SimpleNamespace(  # type: ignore[assignment]
        approve=AsyncMock(),
        request_changes=AsyncMock(),
        comment=AsyncMock(),
        merge=AsyncMock(),
        close_with_comment=AsyncMock(),
        add_line_comment=AsyncMock(),
    )

    with pytest.raises(ValueError):
        await service._run_action_async(  # noqa: SLF001
            action="line_comment",
            pr=_sample_pr(),
            comment="Body",
            merge_method="merge",
            line_path=None,
            line_number=10,
        )


@pytest.mark.asyncio
async def test_run_action_routes_core_actions() -> None:
    service = PRService(settings=AppSettings(config=AppConfig()), token="token")
    service.gateway = SimpleNamespace(  # type: ignore[assignment]
        approve=AsyncMock(),
        request_changes=AsyncMock(),
        comment=AsyncMock(),
        merge=AsyncMock(),
        close_with_comment=AsyncMock(),
        add_line_comment=AsyncMock(),
    )
    pr = _sample_pr()

    await service._run_action_async("approve", pr, "ok", "merge", None, None)  # noqa: SLF001
    await service._run_action_async(
        "request_changes", pr, "fix", "merge", None, None
    )  # noqa: SLF001
    await service._run_action_async("comment", pr, "note", "merge", None, None)  # noqa: SLF001
    await service._run_action_async("merge", pr, None, "squash", None, None)  # noqa: SLF001
    await service._run_action_async("close", pr, "closing", "merge", None, None)  # noqa: SLF001

    service.gateway.approve.assert_awaited_once_with("octo/repo", 1, "ok")  # type: ignore[attr-defined]
    service.gateway.request_changes.assert_awaited_once_with("octo/repo", 1, "fix")  # type: ignore[attr-defined]
    service.gateway.comment.assert_awaited_once_with("octo/repo", 1, "note")  # type: ignore[attr-defined]
    service.gateway.merge.assert_awaited_once_with("octo/repo", 1, "squash")  # type: ignore[attr-defined]
    service.gateway.close_with_comment.assert_awaited_once_with("octo/repo", 1, "closing")  # type: ignore[attr-defined]
