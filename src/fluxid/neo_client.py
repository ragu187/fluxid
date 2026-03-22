from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class NeoApiError(RuntimeError):
    pass


@dataclass
class MarketQuote:
    symbol: str
    ltp: float
    change: float | None = None
    pct_change: float | None = None
    volume: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    source_payload: dict[str, Any] | None = None


class NeoApiClient:
    def __init__(self, base_url: str, api_key: str, access_token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.access_token = access_token

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def get_quote(self, symbol: str) -> MarketQuote:
        payload = await self._fetch_quote_payload(symbol)
        return self._coerce_quote(symbol=symbol, payload=payload)

    async def _fetch_quote_payload(self, symbol: str) -> dict[str, Any]:
        quote_endpoints = [
            "/v1/market/quote",
            "/market/quote",
        ]
        query_keys = ["symbol", "tradingsymbol", "instrument"]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in quote_endpoints:
                for query_key in query_keys:
                    response = await client.get(
                        f"{self.base_url}{endpoint}",
                        params={query_key: symbol},
                        headers=self._headers,
                    )
                    if response.status_code == 404:
                        continue
                    if response.status_code >= 400:
                        raise NeoApiError(
                            f"Neo quote API failure for {symbol}: {response.status_code} {response.text[:160]}"
                        )
                    data = response.json()
                    if isinstance(data, dict):
                        return data

        raise NeoApiError(
            "Unable to locate a compatible quote endpoint. Update NeoApiClient._fetch_quote_payload as per your API contract."
        )

    def _coerce_quote(self, symbol: str, payload: dict[str, Any]) -> MarketQuote:
        source = payload.get("data") if isinstance(payload.get("data"), dict) else payload

        ltp = source.get("ltp") or source.get("last_price") or source.get("lastTradedPrice")
        if ltp is None:
            raise NeoApiError(f"Quote payload for {symbol} missing LTP field: {payload}")

        return MarketQuote(
            symbol=symbol,
            ltp=float(ltp),
            change=_to_float(source.get("change") or source.get("netChange")),
            pct_change=_to_float(source.get("pChange") or source.get("percentChange")),
            volume=_to_float(source.get("volume") or source.get("totalTradedVolume")),
            open=_to_float(
                source.get("open")
                or source.get("openPrice")
                or source.get("open_price")
                or source.get("dayOpen")
            ),
            high=_to_float(
                source.get("high")
                or source.get("highPrice")
                or source.get("high_price")
                or source.get("dayHigh")
            ),
            low=_to_float(
                source.get("low")
                or source.get("lowPrice")
                or source.get("low_price")
                or source.get("dayLow")
            ),
            source_payload=payload,
        )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
