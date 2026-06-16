"""Simple observer service for application events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

EventCallback = Callable[[str, Any], None]


@dataclass
class NotificationService:
    """In-process pub/sub for UI updates."""

    _subscribers: dict[str, list[EventCallback]] = field(default_factory=dict)

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        self._subscribers.setdefault(event_name, []).append(callback)

    def publish(self, event_name: str, payload: Any) -> None:
        for callback in self._subscribers.get(event_name, []):
            callback(event_name, payload)
