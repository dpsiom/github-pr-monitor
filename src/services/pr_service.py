"""PR business logic and monitoring loops."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from src.api.github_client import GitHubRepositoryGateway
from src.api.models import PullRequest
from src.config.settings import AppSettings
from src.services.notification_service import NotificationService
from src.services.webhook_service import WebhookService

PRUpdateCallback = Callable[[list[PullRequest], datetime], None]


class PRService:
    """Coordinates polling and PR actions."""

    def __init__(self, settings: AppSettings, token: str) -> None:
        self.settings = settings
        self.notification_service = NotificationService()
        self.gateway = GitHubRepositoryGateway(settings=settings, token=token)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._refresh_lock = threading.Lock()
        self._webhook_service: WebhookService | None = None

    def subscribe_updates(self, callback: PRUpdateCallback) -> None:
        """Subscribe to PR refresh notifications."""
        self.notification_service.subscribe(
            "prs_updated",
            lambda _n, payload: callback(payload["prs"], payload["ts"]),
        )

    def subscribe_error(self, callback: Callable[[str], None]) -> None:
        """Subscribe to polling errors."""
        self.notification_service.subscribe("polling_error", lambda _n, payload: callback(payload))

    def update_token(self, token: str) -> None:
        """Replace gateway token after re-authentication."""
        self.gateway.token = token

    def start(self) -> None:
        """Start polling in a dedicated daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()

        if self.settings.config.monitor.realtime_mode == "webhook":
            self._webhook_service = WebhookService(
                host=self.settings.config.monitor.webhook_host,
                port=self.settings.config.monitor.webhook_port,
                callback=self._on_webhook_event,
                secret=self.settings.config.monitor.webhook_secret,
            )
            self._webhook_service.start()
            self.notification_service.publish(
                "connection_status",
                (
                    "Webhook listener active at "
                    f"http://{self.settings.config.monitor.webhook_host}:"
                    f"{self.settings.config.monitor.webhook_port}/webhook"
                ),
            )

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop polling loop."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        if self._webhook_service is not None:
            self._webhook_service.stop()

    def _run_loop(self) -> None:
        asyncio.run(self._polling_loop())

    async def _polling_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._refresh_once()
            except Exception as exc:  # noqa: BLE001
                self.notification_service.publish("polling_error", str(exc))

            await asyncio.sleep(self.settings.config.monitor.poll_interval_seconds)

    async def _refresh_once(self) -> None:
        """Refresh monitored PR list once and publish it."""
        repos = [repo.name for repo in self.settings.config.repositories if repo.enabled]
        prs = await self.gateway.fetch_pending_review_prs(repos)
        self.notification_service.publish("prs_updated", {"prs": prs, "ts": datetime.now()})

    def force_refresh(self) -> None:
        """Run an immediate refresh from synchronous code paths."""
        if not self._refresh_lock.acquire(blocking=False):
            return
        try:
            asyncio.run(self._refresh_once())
        except Exception as exc:  # noqa: BLE001
            self.notification_service.publish("polling_error", str(exc))
        finally:
            self._refresh_lock.release()

    def _on_webhook_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Handle incoming webhook events and trigger realtime refresh."""
        actionable_events = {
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
            "check_run",
            "check_suite",
            "issue_comment",
        }
        if event_type not in actionable_events:
            return
        self.notification_service.publish(
            "connection_status",
            f"Webhook event received: {event_type}",
        )
        _ = payload
        self.force_refresh()

    def get_pull_request_details(self, pr: PullRequest) -> PullRequest:
        """Fetch rich PR details for currently selected pull request."""
        return asyncio.run(self.gateway.fetch_pull_request_details(pr))

    def run_action(
        self,
        action: str,
        pr: PullRequest,
        comment: str | None = None,
        merge_method: str = "merge",
        line_path: str | None = None,
        line_number: int | None = None,
    ) -> None:
        """Execute a PR action on a background async task."""
        asyncio.run(
            self._run_action_async(
                action=action,
                pr=pr,
                comment=comment,
                merge_method=merge_method,
                line_path=line_path,
                line_number=line_number,
            )
        )

    async def _run_action_async(
        self,
        action: str,
        pr: PullRequest,
        comment: str | None,
        merge_method: str,
        line_path: str | None,
        line_number: int | None,
    ) -> None:
        if action == "approve":
            await self.gateway.approve(pr.repo, pr.number, comment)
            return
        if action == "request_changes":
            if not comment:
                raise ValueError("Request changes requires a comment")
            await self.gateway.request_changes(pr.repo, pr.number, comment)
            return
        if action == "comment":
            if not comment:
                raise ValueError("Comment cannot be empty")
            await self.gateway.comment(pr.repo, pr.number, comment)
            return
        if action == "merge":
            await self.gateway.merge(pr.repo, pr.number, merge_method)
            return
        if action == "close":
            await self.gateway.close_with_comment(pr.repo, pr.number, comment)
            return
        if action == "line_comment":
            if not comment:
                raise ValueError("Line comment body cannot be empty")
            if not line_path:
                raise ValueError("Line comment path is required")
            if line_number is None:
                raise ValueError("Line number is required")
            await self.gateway.add_line_comment(
                pr.repo,
                pr.number,
                comment,
                line_path,
                line_number,
            )
            return
        raise ValueError(f"Unsupported action: {action}")
