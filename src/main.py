"""Application entry point."""

from __future__ import annotations

import os

from src.config.settings import AppSettings
from src.services.auth_service import AuthService
from src.services.pr_service import PRService
from src.web.app import create_app


def main() -> None:
    """Start the Flask web application."""
    settings = AppSettings.load()
    auth_service = AuthService(settings)
    token: str | None = None
    if settings.config.auth_mode == "browser":
        try:
            token = auth_service.get_or_request_token()
            auth_service.validate_token_scopes(token)
        except ValueError:
            token = None
    else:
        token = auth_service.get_or_request_token()
        auth_service.validate_token_scopes(token)

    pr_service = PRService(settings=settings, token=token)
    if token:
        pr_service.start()

    app = create_app(settings=settings, pr_service=pr_service, auth_service=auth_service)

    host = os.getenv("HOST", "")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"

    app.run(host=host or "0.0.0.0", port=port, debug=debug)  # nosec B104


if __name__ == "__main__":
    main()
