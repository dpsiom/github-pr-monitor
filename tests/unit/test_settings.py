"""Tests for settings loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import AppSettings


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
