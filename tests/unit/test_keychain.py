"""Tests for keychain utility wrappers."""

from __future__ import annotations

from unittest.mock import patch

from src.utils.keychain import get_token_from_keychain, save_token_to_keychain


@patch("src.utils.keychain.keyring.set_password")
def test_save_token_to_keychain(mock_set_password: object) -> None:
    save_token_to_keychain("service", "user", "token")
    mock_set_password.assert_called_once_with("service", "user", "token")


@patch("src.utils.keychain.keyring.get_password", return_value="token")
def test_get_token_from_keychain(mock_get_password: object) -> None:
    token = get_token_from_keychain("service", "user")
    assert token == "token"
    mock_get_password.assert_called_once_with("service", "user")
