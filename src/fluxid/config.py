from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FLUXID_", extra="ignore")

    app_name: str = "Fluxid"
    refresh_seconds: int = 15

    # Kodak Neo API settings
    neo_api_base_url: str = "https://api.kotaksecurities.com/neo"
    neo_api_key: str = Field(default="", description="Kodak/Kotak Neo API key")
    neo_access_token: str = Field(default="", description="Optional bearer token if required")


settings = Settings()
