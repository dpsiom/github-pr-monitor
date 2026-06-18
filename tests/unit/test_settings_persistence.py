"""Tests for settings persistence helpers."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.config.settings import AppConfig, AppSettings, RepositoryConfig


def test_save_config_writes_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    settings = AppSettings(
        config_path=config_path,
        config=AppConfig(repositories=[RepositoryConfig(name="octo/repo", enabled=True)]),
    )

    settings.save_config()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["repositories"][0]["name"] == "octo/repo"


def test_save_config_writes_browser_auth(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    settings = AppSettings(
        config_path=config_path,
        config=AppConfig(
            auth_mode="browser",
            browser_auth={
                "enabled": True,
                "client_id": "Iv1.browser",
                "scopes": "repo read:org",
            },
        ),
    )

    settings.save_config()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["auth_mode"] == "browser"
    assert data["browser_auth"]["client_id"] == "Iv1.browser"
