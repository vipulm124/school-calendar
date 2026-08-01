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

    class Config:
        """
        Load env from the repository .env file and ignore extra env variables.
        """

        env_file = str(Path(__file__).resolve().parents[4] / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


config = Config()
