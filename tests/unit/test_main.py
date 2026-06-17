"""Tests for application entrypoint wiring."""

from __future__ import annotations

from unittest.mock import Mock, patch

import src.main as app_main


def test_main_wires_components() -> None:
    settings = Mock()
    auth = Mock()
    auth.get_or_request_token.return_value = "token"
    pr_service = Mock()
    flask_app = Mock()

    with (
        patch.object(app_main, "AppSettings") as mock_settings_cls,
        patch.object(app_main, "AuthService", return_value=auth) as mock_auth_cls,
        patch.object(app_main, "PRService", return_value=pr_service) as mock_pr_cls,
        patch.object(app_main, "create_app", return_value=flask_app) as mock_create,
    ):
        mock_settings_cls.load.return_value = settings
        app_main.main()

    mock_settings_cls.load.assert_called_once()
    mock_auth_cls.assert_called_once_with(settings)
    auth.validate_token_scopes.assert_called_once_with("token")
    mock_pr_cls.assert_called_once_with(settings=settings, token="token")
    pr_service.start.assert_called_once()
    mock_create.assert_called_once_with(settings=settings, pr_service=pr_service)
    flask_app.run.assert_called_once()
