from __future__ import annotations

import asyncio

import pytest

from fluxid.neo_client import MarketQuote, NeoApiError
from fluxid.service import DashboardService


class StubNeoClient:
    def __init__(self, quotes: dict[str, MarketQuote], fail_symbol: str | None = None) -> None:
        self.quotes = quotes
        self.fail_symbol = fail_symbol

    async def get_quote(self, symbol: str) -> MarketQuote:
        if self.fail_symbol == symbol:
            raise NeoApiError(f"boom: {symbol}")
        return self.quotes[symbol]


def test_load_multi_region_dashboard_data_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxid.service.is_market_day", lambda: True)
    monkeypatch.setattr("fluxid.service.is_us_market_day", lambda: True)
    monkeypatch.setattr("fluxid.service.settings.india_tickers", ("NIFTY_SPOT",))
    monkeypatch.setattr("fluxid.service.settings.us_tickers", ("AAPL",))
    monkeypatch.setattr("fluxid.service.settings.enable_us_feed", True)

    client = StubNeoClient(
        quotes={
            "NIFTY_SPOT": MarketQuote(symbol="NIFTY_SPOT", ltp=24100.0, change=20.0, pct_change=0.08, volume=1_000),
            "AAPL": MarketQuote(symbol="AAPL", ltp=210.0, change=-1.2, pct_change=-0.57, volume=2_000),
        }
    )
    service = DashboardService(neo=client)  # type: ignore[arg-type]

    snapshots = asyncio.run(service.load_multi_region_dashboard_data())

    assert len(snapshots) == 2
    india, us = snapshots
    assert india.region_code == "IN"
    assert india.error_message == ""
    assert india.tickers[0].symbol == "NIFTY_SPOT"
    assert india.tickers[0].display_name == "NIFTY 50"
    assert india.tickers[0].currency == "INR"

    assert us.region_code == "US"
    assert us.error_message == ""
    assert us.tickers[0].symbol == "AAPL"
    assert us.tickers[0].display_name == "Apple"
    assert us.tickers[0].currency == "USD"


def test_load_multi_region_dashboard_data_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxid.service.is_market_day", lambda: True)
    monkeypatch.setattr("fluxid.service.is_us_market_day", lambda: True)
    monkeypatch.setattr("fluxid.service.settings.india_tickers", ("NIFTY_SPOT",))
    monkeypatch.setattr("fluxid.service.settings.us_tickers", ("AAPL",))
    monkeypatch.setattr("fluxid.service.settings.enable_us_feed", True)

    client = StubNeoClient(
        quotes={
            "NIFTY_SPOT": MarketQuote(symbol="NIFTY_SPOT", ltp=24100.0),
            "AAPL": MarketQuote(symbol="AAPL", ltp=210.0),
        },
        fail_symbol="AAPL",
    )
    service = DashboardService(neo=client)  # type: ignore[arg-type]

    snapshots = asyncio.run(service.load_multi_region_dashboard_data())
    india, us = snapshots

    assert india.tickers
    assert us.tickers == []
    assert "boom: AAPL" in us.error_message


def test_load_multi_region_dashboard_data_closed_market(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxid.service.is_market_day", lambda: False)
    monkeypatch.setattr("fluxid.service.is_us_market_day", lambda: False)
    monkeypatch.setattr("fluxid.service.settings.india_tickers", ("NIFTY_SPOT",))
    monkeypatch.setattr("fluxid.service.settings.us_tickers", ("AAPL",))
    monkeypatch.setattr("fluxid.service.settings.enable_us_feed", True)

    client = StubNeoClient(
        quotes={
            "NIFTY_SPOT": MarketQuote(symbol="NIFTY_SPOT", ltp=24100.0),
            "AAPL": MarketQuote(symbol="AAPL", ltp=210.0),
        }
    )
    service = DashboardService(neo=client)  # type: ignore[arg-type]

    snapshots = asyncio.run(service.load_multi_region_dashboard_data())

    for snapshot in snapshots:
        assert snapshot.tickers == []
        assert snapshot.error_message == "Market is closed today."


def test_load_multi_region_dashboard_data_us_feed_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fluxid.service.is_market_day", lambda: True)
    monkeypatch.setattr("fluxid.service.settings.india_tickers", ("NIFTY_SPOT",))
    monkeypatch.setattr("fluxid.service.settings.enable_us_feed", False)

    client = StubNeoClient(
        quotes={
            "NIFTY_SPOT": MarketQuote(symbol="NIFTY_SPOT", ltp=24100.0, change=10.0, pct_change=0.04, volume=500),
        }
    )
    service = DashboardService(neo=client)  # type: ignore[arg-type]

    snapshots = asyncio.run(service.load_multi_region_dashboard_data())

    assert len(snapshots) == 1
    assert snapshots[0].region_code == "IN"
