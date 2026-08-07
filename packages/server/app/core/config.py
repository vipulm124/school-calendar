"""
App wide configuration for all the environments.
This module handles loading of environment variables for the application.
"""

from pathlib import Path
from typing import Optional

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

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()
