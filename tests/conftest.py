"""Common pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import AppConfig, AppSettings


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    """Build isolated settings fixture."""
    return AppSettings(config_path=tmp_path / "config.yaml", config=AppConfig())
