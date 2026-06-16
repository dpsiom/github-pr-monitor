"""Webhook listener service for realtime pull request refresh events."""

from __future__ import annotations

import asyncio
import hmac
import json
import threading
from collections.abc import Callable
from hashlib import sha256
from typing import Any

from aiohttp import web

WebhookCallback = Callable[[str, dict[str, Any]], None]


class WebhookService:
    """Hosts a local webhook endpoint to receive GitHub events."""

    def __init__(
        self,
        host: str,
        port: int,
        callback: WebhookCallback,
        secret: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._callback = callback
        self._secret = secret
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._runner: web.AppRunner | None = None

    def start(self) -> None:
        """Start the webhook HTTP server in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop server and event loop."""
        if not self._loop:
            return
        loop = self._loop
        loop.call_soon_threadsafe(loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_server(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        app = web.Application()
        app.router.add_post("/webhook", self._handle_webhook)

        self._runner = web.AppRunner(app)
        self._loop.run_until_complete(self._runner.setup())
        site = web.TCPSite(self._runner, host=self._host, port=self._port)
        self._loop.run_until_complete(site.start())

        try:
            self._loop.run_forever()
        finally:
            if self._runner:
                self._loop.run_until_complete(self._runner.cleanup())
            self._loop.close()

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        body = await request.read()
        if self._secret and not self._is_valid_signature(request, body):
            return web.Response(status=401, text="invalid signature")

        event_type = request.headers.get("X-GitHub-Event", "unknown")
        payload = json.loads(body.decode("utf-8")) if body else {}
        self._callback(event_type, payload)
        return web.json_response({"ok": True})

    def _is_valid_signature(self, request: web.Request, body: bytes) -> bool:
        if not self._secret:
            return True
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not signature.startswith("sha256="):
            return False
        digest = hmac.new(self._secret.encode("utf-8"), body, sha256).hexdigest()
        return hmac.compare_digest(f"sha256={digest}", signature)
