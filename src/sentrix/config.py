"""Configuration management for Sentrix."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from sentrix.models.position import AlertType


class TelegramConfig(BaseModel):
    """Telegram notification settings."""

    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


class DiscordConfig(BaseModel):
    """Discord notification settings."""

    enabled: bool = False
    webhook_url: str = ""


class LLMConfig(BaseModel):
    """LLM provider settings."""

    provider: str = Field(default="openai", description="'openai' or 'gemini'")
    model: str = Field(default="gpt-4o-mini", description="Model name")
    api_key: str = ""


class AlertRuleConfig(BaseModel):
    """Alert rule configuration."""

    alert_type: AlertType
    threshold: float
    enabled: bool = True
    cooldown_seconds: int = 300


class WatchedAddress(BaseModel):
    """An address to monitor."""

    address: str
    label: str | None = None


class SentinelConfig(BaseModel):
    """Top-level Sentrix configuration."""

    # Network
    network: str = Field(default="mainnet", description="'mainnet' or 'testnet'")

    # Polling
    poll_interval_seconds: int = Field(default=30, ge=5, le=300)

    # Addresses to watch
    addresses: list[WatchedAddress] = Field(default_factory=list)

    # Alert rules
    alert_rules: list[AlertRuleConfig] = Field(
        default_factory=lambda: [
            AlertRuleConfig(
                alert_type=AlertType.LIQUIDATION_WARNING,
                threshold=1.2,
                cooldown_seconds=300,
            ),
            AlertRuleConfig(
                alert_type=AlertType.BALANCE_CHANGE,
                threshold=500.0,
                cooldown_seconds=600,
            ),
            AlertRuleConfig(
                alert_type=AlertType.MARGIN_DEGRADATION,
                threshold=10.0,
                cooldown_seconds=300,
            ),
        ]
    )

    # Notification channels
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)

    # LLM
    llm: LLMConfig = Field(default_factory=LLMConfig)

    # Demo mode
    demo: bool = Field(default=False, description="Use mock data instead of live chain")

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> SentinelConfig:
        """Load config from YAML file, falling back to env vars.

        Priority: CLI args > env vars > YAML file > defaults.
        """
        data: dict = {}

        # 1. Load from YAML file
        if config_path:
            path = Path(config_path)
            if path.exists():
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
        else:
            # Auto-discover config.yaml in CWD
            default_path = Path("config.yaml")
            if default_path.exists():
                with open(default_path) as f:
                    data = yaml.safe_load(f) or {}

        # 2. Override with env vars
        env_overrides = {
            "SENTRIX_NETWORK": "network",
            "SENTRIX_POLL_INTERVAL": "poll_interval_seconds",
            "SENTRIX_DEMO": "demo",
        }
        for env_key, config_key in env_overrides.items():
            val = os.environ.get(env_key)
            if val is not None:
                if config_key == "poll_interval_seconds":
                    data[config_key] = int(val)
                elif config_key == "demo":
                    data[config_key] = val.lower() in ("true", "1", "yes")
                else:
                    data[config_key] = val

        # Telegram from env
        telegram_token = os.environ.get("SENTRIX_TELEGRAM_TOKEN")
        telegram_chat = os.environ.get("SENTRIX_TELEGRAM_CHAT_ID")
        if telegram_token:
            tg = data.get("telegram", {})
            tg["bot_token"] = telegram_token
            tg["enabled"] = True
            if telegram_chat:
                tg["chat_id"] = telegram_chat
            data["telegram"] = tg

        # Discord from env
        discord_url = os.environ.get("SENTRIX_DISCORD_WEBHOOK")
        if discord_url:
            dc = data.get("discord", {})
            dc["webhook_url"] = discord_url
            dc["enabled"] = True
            data["discord"] = dc

        # LLM from env
        llm_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if llm_key:
            llm = data.get("llm", {})
            llm["api_key"] = llm_key
            if os.environ.get("GEMINI_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
                llm["provider"] = "gemini"
                llm["model"] = "gemini-2.0-flash"
            data["llm"] = llm

        # Addresses from env (comma-separated)
        env_addrs = os.environ.get("SENTRIX_ADDRESSES")
        if env_addrs and "addresses" not in data:
            data["addresses"] = [
                {"address": addr.strip()} for addr in env_addrs.split(",") if addr.strip()
            ]

        return cls(**data)
