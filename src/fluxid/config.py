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
    neo_toft_key: str = Field(default="", description="Optional toft key if required")
    india_tickers: tuple[str, ...] = ("NIFTY_SPOT", "BANKNIFTY_SPOT")
    us_tickers: tuple[str, ...] = ("SPY", "QQQ", "DIA", "IWM", "AAPL", "MSFT", "NVDA", "TSLA")
    enable_us_feed: bool = True

    # Opening-bar feature — first 1-minute OHLC candle (9:30–9:31 AM ET).
    # Uses the free Alpaca IEX feed; no paid subscription required.
    # Provide stock/ETF tickers and/or full option-contract symbols supported by Alpaca.
    opening_bar_tickers: tuple[str, ...] = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA")
    opening_bar_option_strikes: tuple[str, ...] = ()

    # Alpaca Market Data API settings (used for the US feed)
    # Free IEX feed: set alpaca_feed="iex" (15-min delayed, no subscription needed).
    # Real-time SIP feed: set alpaca_feed="sip" (requires a paid Alpaca plan).
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    alpaca_api_key_id: str = Field(default="", description="Alpaca API key ID (APCA-API-KEY-ID)")
    alpaca_api_secret_key: str = Field(default="", description="Alpaca API secret key (APCA-API-SECRET-KEY)")
    alpaca_feed: str = Field(default="iex", description="Alpaca data feed: 'iex' (free, delayed) or 'sip' (real-time, paid)")

    @field_validator("india_tickers", "us_tickers", "opening_bar_tickers", "opening_bar_option_strikes", mode="before")
    @classmethod
    def _parse_tickers(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            parts = tuple(part.strip() for part in value.split(",") if part.strip())
            return parts
        if isinstance(value, (list, tuple)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        return tuple()


settings = Settings()
