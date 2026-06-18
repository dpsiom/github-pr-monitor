"""Application settings and YAML configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator


class RepositoryConfig(BaseModel):
    """Repository to monitor."""

    name: str = Field(description="owner/repo format")
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Ensure owner/repo format."""
        clean = value.strip()
        if clean.count("/") != 1:
            raise ValueError("Repository must be in owner/repo format")
        return clean


class MonitorConfig(BaseModel):
    """Monitoring settings."""

    poll_interval_seconds: int = Field(default=60, ge=30)
    realtime_mode: Literal["polling", "webhook"] = "polling"
    smee_url: str | None = None
    webhook_host: str = "127.0.0.1"
    webhook_port: int = Field(default=8765, ge=1, le=65535)
    webhook_secret: str | None = None


class GitHubAppConfig(BaseModel):
    """GitHub App authentication settings."""

    enabled: bool = False
    app_id: str | None = None
    installation_id: str | None = None
    private_key_path: Path | None = None

    @field_validator("private_key_path", mode="before")
    @classmethod
    def normalize_private_key_path(cls, value: str | Path | None) -> Path | None:
        """Normalize private key path strings to Path objects."""
        if value is None:
            return None
        return Path(value)


class BrowserAuthConfig(BaseModel):
    """Browser-based OAuth authentication settings."""

    enabled: bool = False
    client_id: str | None = None
    scopes: str = "repo read:org"


class AppConfig(BaseModel):
    """Config loaded from YAML."""

    repositories: list[RepositoryConfig] = Field(default_factory=list)
    organization_monitoring: bool = False
    organization: str | None = None
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    auth_mode: Literal["pat", "github_app", "browser"] = "browser"
    github_app: GitHubAppConfig = Field(default_factory=GitHubAppConfig)
    browser_auth: BrowserAuthConfig = Field(default_factory=BrowserAuthConfig)


class AppSettings(BaseModel):
    """Runtime settings and loaded config."""

    app_name: str = "GitHub PR Monitor"
    config_path: Path = Path("config.yaml")
    runtime_config_path: Path = Path("runtime_config.yaml")
    token_env_var: str = "GITHUB_TOKEN"
    keychain_service: str = "github-pr-monitor"
    keychain_username: str = "github-token"
    api_base_url: str = "https://api.github.com"
    graphql_url: str = "https://api.github.com/graphql"
    config: AppConfig = Field(default_factory=AppConfig)

    @classmethod
    def load(cls) -> AppSettings:
        """Load settings from environment and YAML config."""
        load_dotenv()
        data_dir = Path(os.environ.get("DATA_DIR", "."))
        settings = cls(runtime_config_path=data_dir / "runtime_config.yaml")
        settings.config = settings._load_yaml_config(settings.config_path)
        settings._apply_runtime_auth_config()
        return settings

    def _apply_runtime_auth_config(self) -> None:
        """Overlay auth settings from the writable runtime config if present."""
        if not self.runtime_config_path.exists():
            return
        try:
            raw = yaml.safe_load(
                self.runtime_config_path.read_text(encoding="utf-8")
            ) or {}
            base = self.config.model_dump(mode="json")
            for key in ("auth_mode", "github_app", "browser_auth"):
                if key in raw:
                    base[key] = raw[key]
            self.config = AppConfig.model_validate(base)
        except (yaml.YAMLError, ValidationError):
            pass  # Malformed runtime config — ignore, don't crash startup

    @staticmethod
    def _load_yaml_config(path: Path) -> AppConfig:
        """Load YAML configuration safely."""
        if not path.exists():
            return AppConfig()

        try:
            raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return AppConfig.model_validate(raw_data)
        except (yaml.YAMLError, ValidationError) as exc:
            raise ValueError(f"Invalid config file: {exc}") from exc

    def save_config(self) -> None:
        """Persist current AppConfig to the main YAML config file."""
        payload = self.config.model_dump(mode="json")
        self.config_path.write_text(
            yaml.safe_dump(payload, sort_keys=False),
            encoding="utf-8",
        )

    def save_auth_config(self) -> None:
        """Persist auth settings to the writable runtime config file."""
        payload = {
            "auth_mode": self.config.auth_mode,
            "github_app": self.config.github_app.model_dump(mode="json"),
            "browser_auth": self.config.browser_auth.model_dump(mode="json"),
        }
        self.runtime_config_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_config_path.write_text(
            yaml.safe_dump(payload, sort_keys=False),
            encoding="utf-8",
        )
