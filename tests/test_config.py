"""Tests for the configuration system."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from inj_sentinel.config import SentinelConfig
from inj_sentinel.models.position import AlertType


class TestSentinelConfig:
    """Tests for configuration loading."""

    def test_default_config(self) -> None:
        """Default config should have sensible values."""
        config = SentinelConfig()
        assert config.network == "mainnet"
        assert config.poll_interval_seconds == 30
        assert config.demo is False
        assert len(config.alert_rules) > 0

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """Should load settings from YAML file."""
        yaml_content = """
network: testnet
poll_interval_seconds: 60
demo: true
addresses:
  - address: inj1test
    label: Test
alert_rules:
  - alert_type: liquidation_warning
    threshold: 1.5
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        config = SentinelConfig.load(config_file)
        assert config.network == "testnet"
        assert config.poll_interval_seconds == 60
        assert config.demo is True
        assert len(config.addresses) == 1
        assert config.addresses[0].address == "inj1test"

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables should override YAML settings."""
        monkeypatch.setenv("INJ_SENTINEL_NETWORK", "testnet")
        monkeypatch.setenv("INJ_SENTINEL_DEMO", "true")
        monkeypatch.setenv("INJ_SENTINEL_POLL_INTERVAL", "120")

        config = SentinelConfig.load()
        assert config.network == "testnet"
        assert config.demo is True
        assert config.poll_interval_seconds == 120

    def test_telegram_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Telegram config from env vars."""
        monkeypatch.setenv("INJ_SENTINEL_TELEGRAM_TOKEN", "test_token")
        monkeypatch.setenv("INJ_SENTINEL_TELEGRAM_CHAT_ID", "123456")

        config = SentinelConfig.load()
        assert config.telegram.enabled is True
        assert config.telegram.bot_token == "test_token"
        assert config.telegram.chat_id == "123456"

    def test_addresses_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Addresses from comma-separated env var."""
        monkeypatch.setenv("INJ_SENTINEL_ADDRESSES", "inj1aaa,inj1bbb")

        config = SentinelConfig.load()
        assert len(config.addresses) == 2
        assert config.addresses[0].address == "inj1aaa"
        assert config.addresses[1].address == "inj1bbb"

    def test_missing_yaml_uses_defaults(self) -> None:
        """Non-existent YAML path should use defaults."""
        config = SentinelConfig.load("/nonexistent/path.yaml")
        assert config.network == "mainnet"

    def test_default_alert_rules(self) -> None:
        """Default config should have liquidation and balance rules."""
        config = SentinelConfig()
        types = [r.alert_type for r in config.alert_rules]
        assert AlertType.LIQUIDATION_WARNING in types
        assert AlertType.BALANCE_CHANGE in types

    def test_openai_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OpenAI API key from env."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")

        config = SentinelConfig.load()
        assert config.llm.api_key == "sk-test123"
        assert config.llm.provider == "openai"

    def test_gemini_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Gemini API key from env (without OpenAI)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-test123")

        config = SentinelConfig.load()
        assert config.llm.api_key == "gemini-test123"
        assert config.llm.provider == "gemini"
