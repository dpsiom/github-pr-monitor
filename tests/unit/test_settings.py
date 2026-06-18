"""Tests for settings loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import AppConfig, AppSettings


def test_settings_loads_default_when_missing(tmp_path: Path) -> None:
    settings = AppSettings(config_path=tmp_path / "missing.yaml")
    loaded = settings._load_yaml_config(settings.config_path)
    assert loaded.repositories == []


def test_settings_rejects_invalid_repository(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("repositories:\n  - name: invalid\n", encoding="utf-8")

    with pytest.raises(ValueError):
        AppSettings._load_yaml_config(config_file)


def test_settings_parses_github_app_private_key_path(tmp_path: Path) -> None:
    key_path = tmp_path / "app-private-key.pem"
    key_path.write_text("dummy", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        (
            "auth_mode: github_app\n"
            "github_app:\n"
            "  enabled: true\n"
            "  app_id: '123'\n"
            "  installation_id: '456'\n"
            f"  private_key_path: '{key_path}'\n"
        ),
        encoding="utf-8",
    )

    loaded = AppSettings._load_yaml_config(config_file)
    assert loaded.auth_mode == "github_app"
    assert loaded.github_app.private_key_path == key_path


def test_settings_parses_browser_auth(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        (
            "auth_mode: browser\n"
            "browser_auth:\n"
            "  enabled: true\n"
            "  client_id: 'Iv1.browser'\n"
            "  scopes: 'repo read:org'\n"
        ),
        encoding="utf-8",
    )

    loaded = AppSettings._load_yaml_config(config_file)
    assert loaded.auth_mode == "browser"
    assert loaded.browser_auth.enabled is True
    assert loaded.browser_auth.client_id == "Iv1.browser"


def test_runtime_config_overlays_auth_fields(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "repositories:\n  - name: octo/repo\n    enabled: true\n",
        encoding="utf-8",
    )
    runtime_file = tmp_path / "runtime_config.yaml"
    runtime_file.write_text(
        (
            "auth_mode: browser\n"
            "browser_auth:\n"
            "  enabled: true\n"
            "  client_id: 'Iv1.runtime'\n"
            "  scopes: 'repo read:org'\n"
        ),
        encoding="utf-8",
    )

    settings = AppSettings(
        config_path=config_file,
        runtime_config_path=runtime_file,
    )
    settings.config = AppSettings._load_yaml_config(config_file)
    settings._apply_runtime_auth_config()

    # Auth fields come from runtime config
    assert settings.config.auth_mode == "browser"
    assert settings.config.browser_auth.client_id == "Iv1.runtime"
    # Repos still come from config.yaml
    assert settings.config.repositories[0].name == "octo/repo"


def test_runtime_config_missing_does_not_crash(tmp_path: Path) -> None:
    settings = AppSettings(
        config_path=tmp_path / "config.yaml",
        runtime_config_path=tmp_path / "runtime_config.yaml",
    )
    settings.config = AppConfig()
    settings._apply_runtime_auth_config()  # should not raise
    assert settings.config.auth_mode == "browser"  # default unchanged
