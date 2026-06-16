"""Tests for notification pub/sub service."""

from __future__ import annotations

from src.services.notification_service import NotificationService


def test_publish_notifies_subscriber() -> None:
    service = NotificationService()
    received: list[tuple[str, str]] = []

    service.subscribe("event", lambda name, payload: received.append((name, payload)))
    service.publish("event", "payload")

    assert received == [("event", "payload")]
