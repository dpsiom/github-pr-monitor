"""OS keychain wrappers."""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError


def save_token_to_keychain(service_name: str, username: str, token: str) -> None:
    """Store token in OS keychain if a backend is available."""
    try:
        keyring.set_password(service_name, username, token)
    except KeyringError:
        # Containers often have no OS keyring backend. Browser auth can still
        # proceed for the running process without persistent token storage.
        return


def get_token_from_keychain(service_name: str, username: str) -> str | None:
    """Read token from OS keychain if available."""
    try:
        return keyring.get_password(service_name, username)
    except KeyringError:
        return None
