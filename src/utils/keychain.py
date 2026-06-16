"""OS keychain wrappers."""

from __future__ import annotations

import keyring


def save_token_to_keychain(service_name: str, username: str, token: str) -> None:
    """Store token in OS keychain."""
    keyring.set_password(service_name, username, token)


def get_token_from_keychain(service_name: str, username: str) -> str | None:
    """Read token from OS keychain."""
    return keyring.get_password(service_name, username)
