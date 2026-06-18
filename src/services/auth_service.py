"""Authentication and token validation service."""

from __future__ import annotations

import os
import time
import webbrowser

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
        if self.settings.config.auth_mode == "browser":
            token = get_token_from_keychain(
                service_name=self.settings.keychain_service,
                username=self.settings.keychain_username,
            )
            if token:
                return token

            raise ValueError(
                "Browser auth token not found in keychain. "
                "Open Settings and run Browser Authentication."
            )

        token = os.getenv(self.settings.token_env_var)
        if token:
            return token.strip()

        token = get_token_from_keychain(
            service_name=self.settings.keychain_service,
            username=self.settings.keychain_username,
        )
        if token:
            return token

        raise ValueError(
            "GitHub token is required. Set GITHUB_TOKEN environment variable "
            "or store it in the OS keychain."
        )

    def begin_browser_device_flow(self) -> dict[str, str | int]:
        """Request a device-flow code and verification URL from GitHub."""
        browser = self.settings.config.browser_auth
        if self.settings.config.auth_mode != "browser":
            raise ValueError("auth_mode must be set to browser to use browser auth")
        if not browser.enabled:
            raise ValueError("browser_auth.enabled must be true when auth_mode=browser")
        if not browser.client_id:
            raise ValueError("browser_auth.client_id is required")

        code_response = requests.post(
            "https://github.com/login/device/code",
            data={
                "client_id": browser.client_id,
                "scope": browser.scopes,
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "github-pr-monitor",
            },
            timeout=20,
        )
        code_response.raise_for_status()
        code_payload = code_response.json()
        device_code = code_payload.get("device_code")
        user_code = code_payload.get("user_code")
        interval = code_payload.get("interval", 5)
        expires_in = code_payload.get("expires_in", 900)
        verification_url = code_payload.get("verification_uri_complete") or code_payload.get(
            "verification_uri"
        )

        if not isinstance(device_code, str) or not device_code:
            raise PermissionError("Failed to start browser authentication")
        if not isinstance(user_code, str) or not user_code:
            raise PermissionError("Missing user code for browser authentication")
        if not isinstance(verification_url, str) or not verification_url:
            raise PermissionError("Missing verification URL for browser authentication")

        return {
            "device_code": device_code,
            "user_code": user_code,
            "verification_url": verification_url,
            "interval": int(interval),
            "expires_in": int(expires_in),
        }

    def complete_browser_device_flow(
        self,
        *,
        device_code: str,
        interval: int,
        expires_in: int,
        open_browser: bool = True,
        verification_url: str | None = None,
        single_check: bool = False,
    ) -> str:
        """Poll device-flow token endpoint until an access token is returned."""
        browser = self.settings.config.browser_auth
        if self.settings.config.auth_mode != "browser":
            raise ValueError("auth_mode must be set to browser to use browser auth")
        if not browser.enabled:
            raise ValueError("browser_auth.enabled must be true when auth_mode=browser")
        if not browser.client_id:
            raise ValueError("browser_auth.client_id is required")

        if open_browser and verification_url:
            webbrowser.open(verification_url)

        deadline = time.time() + int(expires_in)
        poll_interval = int(interval)

        while time.time() < deadline:
            token_response = requests.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": browser.client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": "github-pr-monitor",
                },
                timeout=20,
            )
            token_response.raise_for_status()
            token_payload = token_response.json()

            token = token_payload.get("access_token")
            if isinstance(token, str) and token:
                save_token_to_keychain(
                    service_name=self.settings.keychain_service,
                    username=self.settings.keychain_username,
                    token=token,
                )
                return token

            error_code = token_payload.get("error")
            if error_code == "authorization_pending":
                if single_check:
                    raise PermissionError("Browser authentication pending")
                time.sleep(poll_interval)
                continue
            if error_code == "slow_down":
                if single_check:
                    raise PermissionError("Browser authentication pending")
                poll_interval += 5
                time.sleep(poll_interval)
                continue
            if error_code == "expired_token":
                raise PermissionError("Browser authentication expired before completion")
            if error_code == "access_denied":
                raise PermissionError("Browser authentication was denied")

            raise PermissionError("Browser authentication failed")

        raise PermissionError("Browser authentication timed out")

    def authenticate_browser_session(self, open_browser: bool = True) -> str:
        """Run OAuth device flow and store resulting token in keychain."""
        flow = self.begin_browser_device_flow()
        return self.complete_browser_device_flow(
            device_code=str(flow["device_code"]),
            interval=int(flow["interval"]),
            expires_in=int(flow["expires_in"]),
            open_browser=open_browser,
            verification_url=str(flow["verification_url"]),
        )

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

        if self.settings.config.auth_mode in {"pat", "browser"}:
            scopes = response.headers.get("X-OAuth-Scopes", "")
            # Fine-grained PATs do not populate X-OAuth-Scopes (the header is
            # absent or empty). Only enforce scope check for classic PATs that
            # actually advertise their scopes.
            if scopes:
                scope_set = {s.strip() for s in scopes.split(",") if s.strip()}
                if "repo" not in scope_set:
                    raise PermissionError("Token is missing required repo scope")
