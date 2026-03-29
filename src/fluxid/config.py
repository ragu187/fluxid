from __future__ import annotations

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FLUXID_", extra="ignore")

    app_name: str = "Fluxid"
    refresh_seconds: int = 15

    # Kotak Neo API settings
    neo_api_base_url: str = "https://api.kotaksecurities.com/neo"
    neo_api_key: str = Field(default="", description="Kotak Neo API key")
    neo_access_token: str = Field(default="", description="Optional bearer token if required")
    india_tickers: tuple[str, ...] = ("NIFTY_SPOT", "BANKNIFTY_SPOT")
    us_tickers: tuple[str, ...] = ("SPY", "QQQ", "DIA", "IWM", "AAPL", "MSFT", "NVDA", "TSLA")
    enable_us_feed: bool = True

    @field_validator("india_tickers", "us_tickers", mode="before")
    @classmethod
    def _parse_tickers(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            parts = tuple(part.strip() for part in value.split(",") if part.strip())
            return parts
        if isinstance(value, (list, tuple)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        return tuple()


settings = Settings()
