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


def test_save_auth_config_writes_only_auth_fields(tmp_path: Path) -> None:
    runtime_path = tmp_path / "data" / "runtime_config.yaml"
    settings = AppSettings(
        runtime_config_path=runtime_path,
        config=AppConfig(
            repositories=[RepositoryConfig(name="octo/repo", enabled=True)],
            auth_mode="browser",
            browser_auth={
                "enabled": True,
                "client_id": "Iv1.browser",
                "scopes": "repo read:org",
            },
        ),
    )

    settings.save_auth_config()

    data = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    assert data["auth_mode"] == "browser"
    assert data["browser_auth"]["client_id"] == "Iv1.browser"
    # Repos must NOT be written to the runtime config
    assert "repositories" not in data


def test_save_auth_config_creates_parent_directory(tmp_path: Path) -> None:
    runtime_path = tmp_path / "nested" / "dir" / "runtime_config.yaml"
    settings = AppSettings(
        runtime_config_path=runtime_path,
        config=AppConfig(auth_mode="browser"),
    )

    settings.save_auth_config()

    assert runtime_path.exists()
