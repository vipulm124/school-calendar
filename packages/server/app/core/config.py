"""
App wide configuration for all the environments.
This module handles loading of environment variables for the application.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


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

    class Config:
        """
        Load env from the repository .env file and ignore extra env variables.
        """

        env_file = str(Path(__file__).resolve().parents[4] / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


config = Config()
