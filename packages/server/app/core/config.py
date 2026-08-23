"""
App wide configuration for all the environments.
This module handles loading of environment variables for the application.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Optional[str]:
    """
    Locate a .env file without assuming a fixed repo depth.

    Local layout: packages/server/app/core/config.py → repo root .env
    Docker layout: /app/core/config.py → often no .env; OS env vars are used instead
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)

    cwd_candidate = Path.cwd() / ".env"
    if cwd_candidate.is_file():
        return str(cwd_candidate)
    return None


class Config(BaseSettings):
    """
    Configurations class that loads environment variables.
    Provides type-safe access to environment variables used across the application.
    """

    DATABASE_URL: str = "sqlite:///./school_calendar.db"
    SQLALCHEMY_ECHO: bool = False
    ENV: str = "development"
    ORIGIN: str = "http://localhost:3000"

    # Azure AI Foundry / Azure OpenAI (vision-capable chat model)
    # Prefer values from .env — do not hardcode secrets here.
    # Endpoint examples:
    #   https://<resource>.services.ai.azure.com
    #   https://<resource>.services.ai.azure.com/openai/v1
    #   https://<resource>.openai.azure.com
    AZURE_FOUNDRY_ENDPOINT: str = ""
    AZURE_FOUNDRY_API_KEY: str = ""
    AZURE_FOUNDRY_DEPLOYMENT: str = "gpt-4o-mini"
    # For OpenAI v1 routes use "v1" (or leave blank). Date-style versions are legacy.
    AZURE_FOUNDRY_API_VERSION: str = "v1"

    # Telegram bot
    TELEGRAM_BOT_TOKEN: str = ""

    # Telegram admin user ids. In .env use either:
    #   ADMIN_USER_ID='["8057453587","123"]'   (JSON list — preferred)
    #   ADMIN_USER_ID=8057453587,123           (comma-separated)
    ADMIN_USER_ID: list[str] = []

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ADMIN_USER_ID", mode="before")
    @classmethod
    def parse_admin_user_ids(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, (int, float)):
            return [str(int(value))]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError("ADMIN_USER_ID JSON must be a list")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [part.strip() for part in text.split(",") if part.strip()]
        raise ValueError("ADMIN_USER_ID must be a list or comma-separated string")


config = Config()
