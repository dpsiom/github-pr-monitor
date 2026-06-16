"""Application entry point."""

from src.config.settings import AppSettings
from src.services.auth_service import AuthService
from src.services.pr_service import PRService
from src.ui.app import PRMonitorApp


def main() -> None:
    """Start the desktop application."""
    settings = AppSettings.load()
    auth_service = AuthService(settings)
    token = auth_service.get_or_request_token()
    auth_service.validate_token_scopes(token)

    pr_service = PRService(settings=settings, token=token)
    app = PRMonitorApp(settings=settings, pr_service=pr_service)
    app.run()


if __name__ == "__main__":
    main()
