"""Authentication and token validation service."""

from __future__ import annotations

import os
import time

import jwt
import requests

from src.config.settings import AppSettings
from src.utils.keychain import get_token_from_keychain, save_token_to_keychain


class AuthService:
    """Handles token retrieval from env, keychain, or first-run prompt."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def get_or_request_token(self) -> str:
        """Resolve token from secure sources."""
        if self.settings.config.auth_mode == "github_app":
            return self._get_github_app_token()

        token = os.getenv(self.settings.token_env_var)
        if token:
            return token.strip()

        token = get_token_from_keychain(
            service_name=self.settings.keychain_service,
            username=self.settings.keychain_username,
        )
        if token:
            return token

        # Import lazily so headless test environments can import this module.
        from tkinter import simpledialog

        entered = simpledialog.askstring(
            title="GitHub Token Required",
            prompt="Enter GitHub PAT (repo scope required):",
            show="*",
        )
        if not entered:
            raise ValueError("GitHub token is required")

        safe_token = entered.strip()
        save_token_to_keychain(
            service_name=self.settings.keychain_service,
            username=self.settings.keychain_username,
            token=safe_token,
        )
        return safe_token

    def _get_github_app_token(self) -> str:
        """Create and exchange a GitHub App JWT for an installation token."""
        app = self.settings.config.github_app
        if not app.enabled:
            raise ValueError("github_app.enabled must be true when auth_mode=github_app")
        if not app.app_id or not app.installation_id:
            raise ValueError("GitHub App app_id and installation_id are required")
        if not app.private_key_path or not app.private_key_path.exists():
            raise ValueError("GitHub App private_key_path is missing or does not exist")

        private_key = app.private_key_path.read_text(encoding="utf-8")
        now = int(time.time())
        encoded_jwt = jwt.encode(
            {
                "iat": now - 60,
                "exp": now + 9 * 60,
                "iss": app.app_id,
            },
            private_key,
            algorithm="RS256",
        )

        response = requests.post(
            f"{self.settings.api_base_url}/app/installations/{app.installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {encoded_jwt}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "github-pr-monitor",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise PermissionError("Failed to obtain GitHub App installation token")
        return token

    def validate_token_scopes(self, token: str) -> None:
        """Validate required scopes on startup."""
        response = requests.get(
            f"{self.settings.api_base_url}/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "github-pr-monitor",
            },
            timeout=20,
        )
        if response.status_code == 401:
            raise PermissionError("Invalid GitHub token")
        response.raise_for_status()

        if self.settings.config.auth_mode == "pat":
            scopes = response.headers.get("X-OAuth-Scopes", "")
            # Fine-grained PATs do not populate X-OAuth-Scopes (the header is
            # absent or empty). Only enforce scope check for classic PATs that
            # actually advertise their scopes.
            if scopes:
                scope_set = {s.strip() for s in scopes.split(",") if s.strip()}
                if "repo" not in scope_set:
                    raise PermissionError("Token is missing required repo scope")
