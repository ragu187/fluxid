"""Alpaca Market Data client for US equities.

Uses the Alpaca Data API v2 snapshot endpoint to retrieve last-trade price,
OHLC, volume and previous-close for a single US stock or ETF symbol.

Authentication
--------------
Set ``FLUXID_ALPACA_API_KEY_ID`` and ``FLUXID_ALPACA_API_SECRET_KEY`` in the
environment (or ``.env`` file).

Feed tiers
----------
``feed=iex``  – free tier, 15-minute delayed IEX data (default).
``feed=sip``  – consolidated SIP feed, real-time (requires paid Alpaca plan).
``feed=indicative`` – pre/post-market indicative quotes.

Set ``FLUXID_ALPACA_FEED=sip`` to upgrade to real-time once you have a paid
Alpaca subscription.
"""

from __future__ import annotations

from typing import Any

import httpx

from fluxid.neo_client import MarketQuote, QuoteProvider


class AlpacaApiError(RuntimeError):
    pass


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
