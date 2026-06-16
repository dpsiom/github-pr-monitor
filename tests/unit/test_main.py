"""Tests for application entrypoint wiring."""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock, patch


def test_main_wires_components() -> None:
    fake_ui_module = types.ModuleType("src.ui.app")
    fake_ui_module.PRMonitorApp = Mock()
    with patch.dict(sys.modules, {"src.ui.app": fake_ui_module}):
        import src.main as app_main

        settings = Mock()
        auth = Mock()
        auth.get_or_request_token.return_value = "token"
        app = Mock()

        with (
            patch.object(app_main.AppSettings, "load", return_value=settings) as mock_load,
            patch.object(app_main, "AuthService", return_value=auth) as mock_auth_cls,
            patch.object(app_main, "PRService") as mock_pr_service_cls,
            patch.object(app_main, "PRMonitorApp", return_value=app) as mock_app_cls,
        ):
            app_main.main()

    mock_load.assert_called_once()
    mock_auth_cls.assert_called_once_with(settings)
    auth.validate_token_scopes.assert_called_once_with("token")
    mock_pr_service_cls.assert_called_once()
    mock_app_cls.assert_called_once()
    app.run.assert_called_once()
