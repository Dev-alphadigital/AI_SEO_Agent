"""Configuration management using Pydantic Settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "AI SEO Agent"
    api_port: int = 8000
    ahrefs_api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback"
    token_file: str = "tokens.json"
    credentials_file: str = "credentials.json"
    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-r1-0528:free"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
