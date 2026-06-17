"""Tests for authentication flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.config.settings import AppConfig, AppSettings, GitHubAppConfig
from src.services.auth_service import AuthService


def test_get_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "abc123")
    auth = AuthService(AppSettings())
    assert auth.get_or_request_token() == "abc123"


@patch("src.services.auth_service.requests.get")
def test_validate_token_scope_missing_repo(mock_get: Mock) -> None:
    response = Mock()
    response.status_code = 200
    response.headers = {"X-OAuth-Scopes": "read:user"}
    response.raise_for_status = Mock()
    mock_get.return_value = response

    auth = AuthService(AppSettings())
    with pytest.raises(PermissionError):
        auth.validate_token_scopes("token")


@patch("src.services.auth_service.requests.post")
@patch("src.services.auth_service.jwt.encode")
def test_github_app_token_exchange(mock_jwt_encode: Mock, mock_post: Mock, tmp_path: Path) -> None:
    key_path = tmp_path / "app-key.pem"
    key_path.write_text("private-key", encoding="utf-8")

    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"token": "ghs_installation_token"}
    mock_post.return_value = response
    mock_jwt_encode.return_value = "signed-jwt"

    settings = AppSettings(
        config=AppConfig(
            auth_mode="github_app",
            github_app=GitHubAppConfig(
                enabled=True,
                app_id="123",
                installation_id="456",
                private_key_path=key_path,
            ),
        )
    )
    auth = AuthService(settings)
    token = auth.get_or_request_token()

    assert token == "ghs_installation_token"
    mock_post.assert_called_once()


@patch("src.services.auth_service.requests.get")
def test_validate_token_scope_skipped_for_github_app(mock_get: Mock) -> None:
    response = Mock()
    response.status_code = 200
    response.headers = {"X-OAuth-Scopes": ""}
    response.raise_for_status = Mock()
    mock_get.return_value = response

    settings = AppSettings(config=AppConfig(auth_mode="github_app"))
    auth = AuthService(settings)
    auth.validate_token_scopes("token")


@patch("src.services.auth_service.get_token_from_keychain", return_value="keychain-token")
def test_get_token_from_keychain(mock_keychain: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    auth = AuthService(AppSettings())
    assert auth.get_or_request_token() == "keychain-token"
    mock_keychain.assert_called_once()


@patch("src.services.auth_service.get_token_from_keychain", return_value=None)
def test_get_token_raises_when_no_source(
    mock_keychain: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    auth = AuthService(AppSettings())
    with pytest.raises(ValueError, match="GitHub token is required"):
        auth.get_or_request_token()
    mock_keychain.assert_called_once()


@patch("src.services.auth_service.requests.get")
def test_validate_token_unauthorized(mock_get: Mock) -> None:
    response = Mock()
    response.status_code = 401
    response.headers = {}
    response.raise_for_status = Mock()
    mock_get.return_value = response

    auth = AuthService(AppSettings())
    with pytest.raises(PermissionError):
        auth.validate_token_scopes("token")


def test_github_app_config_validation_errors() -> None:
    auth = AuthService(AppSettings(config=AppConfig(auth_mode="github_app")))

    with pytest.raises(ValueError):
        auth._get_github_app_token()  # noqa: SLF001


@patch("src.services.auth_service.requests.post")
@patch("src.services.auth_service.jwt.encode", return_value="jwt")
def test_github_app_token_missing_token_field(
    mock_jwt_encode: Mock,
    mock_post: Mock,
    tmp_path: Path,
) -> None:
    _ = mock_jwt_encode
    key_path = tmp_path / "app-key.pem"
    key_path.write_text("private-key", encoding="utf-8")

    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {}
    mock_post.return_value = response

    settings = AppSettings(
        config=AppConfig(
            auth_mode="github_app",
            github_app=GitHubAppConfig(
                enabled=True,
                app_id="123",
                installation_id="456",
                private_key_path=key_path,
            ),
        )
    )
    auth = AuthService(settings)

    with pytest.raises(PermissionError):
        auth.get_or_request_token()
