"""Alpaca Market Data client for US equities.

Uses the Alpaca Data API v2 snapshot endpoint to retrieve last-trade price,
OHLC, volume and previous-close for a single US stock or ETF symbol.

Also exposes :meth:`AlpacaApiClient.get_first_minute_bar` which fetches the
9:30 AM opening 1-minute candle (OHLC + volume) for any US stock/ETF using
the free IEX feed — no paid subscription required.  The bar is a completed
historical record by 9:31 AM ET, so no streaming connection is needed.

Authentication
--------------
Set ``FLUXID_ALPACA_API_KEY_ID`` and ``FLUXID_ALPACA_API_SECRET_KEY`` in the
environment (or ``.env`` file).

Feed tiers
----------
``feed=iex``  – free tier, IEX data (default).
``feed=sip``  – consolidated SIP feed, real-time (requires paid Alpaca plan).
``feed=indicative`` – pre/post-market indicative quotes.

Set ``FLUXID_ALPACA_FEED=sip`` to upgrade to real-time once you have a paid
Alpaca subscription.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from fluxid.neo_client import MarketQuote, QuoteProvider

_ET = ZoneInfo("America/New_York")


class AlpacaApiError(RuntimeError):
    pass


@dataclass
class FirstMinuteBar:
    """OHLC data for the 9:30 AM opening 1-minute candle of a US equity."""

    symbol: str
    bar_time: str       # ISO-8601 timestamp of the bar open (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class AlpacaApiClient:
    """Thin async HTTP client for the Alpaca Market Data v2 snapshot endpoint."""

    def __init__(
        self,
        base_url: str,
        key_id: str,
        secret_key: str,
        feed: str = "iex",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.key_id = key_id
        self.secret_key = secret_key
        self.feed = feed

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
        }

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch a :class:`~fluxid.neo_client.MarketQuote` for *symbol* from Alpaca."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/v2/stocks/snapshots",
                params={"symbols": symbol, "feed": self.feed},
                headers=self._headers,
            )
        if response.status_code >= 400:
            raise AlpacaApiError(
                f"Alpaca snapshot API failure for {symbol}: {response.status_code} {response.text[:160]}"
            )
        data = response.json()
        snap = data.get(symbol)
        if snap is None:
            raise AlpacaApiError(f"No snapshot returned by Alpaca for {symbol!r}")
        return self._coerce_snapshot(symbol, snap)

    async def get_first_minute_bar(
        self, symbol: str, trade_date: date | None = None
    ) -> FirstMinuteBar:
        """Fetch the 9:30 AM opening 1-minute OHLC bar for *symbol*.

        The bar covering 9:30–9:31 AM US/Eastern is a completed historical
        record by 9:31 AM, so no real-time streaming subscription is needed —
        the free Alpaca IEX feed is sufficient.

        Args:
            symbol:     US stock or ETF ticker, e.g. ``"AAPL"``.
            trade_date: The session date.  Defaults to today in US/Eastern.

        Returns:
            A :class:`FirstMinuteBar` with open, high, low, close and volume.

        Raises:
            :class:`AlpacaApiError`: when the API call fails or no bar data
            is available for the requested session.
        """
        if trade_date is None:
            trade_date = datetime.now(tz=_ET).date()
        bar_start = datetime(
            trade_date.year, trade_date.month, trade_date.day, 9, 30, 0, tzinfo=_ET
        )
        bar_end = bar_start + timedelta(minutes=1)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/v2/stocks/{symbol}/bars",
                params={
                    "timeframe": "1Min",
                    "start": bar_start.isoformat(),
                    "end": bar_end.isoformat(),
                    "limit": 1,
                    "feed": self.feed,
                },
                headers=self._headers,
            )
        if response.status_code >= 400:
            raise AlpacaApiError(
                f"Alpaca bars API failure for {symbol}: {response.status_code} {response.text[:160]}"
            )
        data = response.json()
        bars = data.get("bars") or []
        if not bars:
            raise AlpacaApiError(
                f"No opening bar returned by Alpaca for {symbol!r} on {trade_date}"
            )
        return self._coerce_bar(symbol, bars[0])

    def _coerce_snapshot(self, symbol: str, snap: dict[str, Any]) -> MarketQuote:
        """Map an Alpaca snapshot dict to a :class:`~fluxid.neo_client.MarketQuote`.

        Fields extracted:

        * ``latestTrade.p``  → ``ltp``
        * ``dailyBar.o/h/l`` → ``open`` / ``high`` / ``low``
        * ``dailyBar.v``     → ``volume``
        * ``prevDailyBar.c`` → previous close used to compute ``change`` / ``pct_change``
        """
        latest_trade = snap.get("latestTrade") or {}
        daily_bar = snap.get("dailyBar") or {}
        prev_daily_bar = snap.get("prevDailyBar") or {}

        ltp = _to_float(latest_trade.get("p"))
        if ltp is None:
            raise AlpacaApiError(
                f"Alpaca snapshot for {symbol!r} missing trade price field 'p': {snap}"
            )

        prev_close = _to_float(prev_daily_bar.get("c"))
        if prev_close is not None and prev_close != 0:
            change = ltp - prev_close
            pct_change = change / prev_close * 100
        else:
            change = None
            pct_change = None

        return MarketQuote(
            symbol=symbol,
            ltp=ltp,
            change=change,
            pct_change=pct_change,
            volume=_to_float(daily_bar.get("v")),
            open=_to_float(daily_bar.get("o")),
            high=_to_float(daily_bar.get("h")),
            low=_to_float(daily_bar.get("l")),
            source_payload=snap,
        )

    def _coerce_bar(self, symbol: str, bar: dict[str, Any]) -> FirstMinuteBar:
        """Map an Alpaca bar dict to a :class:`FirstMinuteBar`.

        Fields extracted:

        * ``t`` → ``bar_time`` (ISO-8601 timestamp)
        * ``o`` → ``open``
        * ``h`` → ``high``
        * ``l`` → ``low``
        * ``c`` → ``close``
        * ``v`` → ``volume``
        """
        bar_time = bar.get("t") or ""
        open_ = _to_float(bar.get("o"))
        high = _to_float(bar.get("h"))
        low = _to_float(bar.get("l"))
        close = _to_float(bar.get("c"))
        if open_ is None or high is None or low is None or close is None:
            raise AlpacaApiError(
                f"Alpaca bar for {symbol!r} missing required OHLC fields: {bar}"
            )
        return FirstMinuteBar(
            symbol=symbol,
            bar_time=bar_time,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=_to_float(bar.get("v")),
        )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class AlpacaQuoteProvider:
    """Adapts :class:`AlpacaApiClient` to the :class:`~fluxid.neo_client.QuoteProvider`
    protocol for US instruments.

    The *region* parameter required by the protocol is intentionally ignored:
    this provider is US-only and is never registered for other regions.
    """

    def __init__(self, client: AlpacaApiClient) -> None:
        self._client = client

    async def get_quote(self, symbol: str, region: str) -> MarketQuote:  # noqa: ARG002
        return await self._client.get_quote(symbol)
