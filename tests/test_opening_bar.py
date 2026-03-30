"""Tests for DashboardService.load_opening_bar_data."""
from __future__ import annotations

import asyncio
from datetime import date

import pytest

from fluxid.alpaca_client import AlpacaApiError, AlpacaApiClient, FirstMinuteBar
from fluxid.service import DashboardService, OpeningBarSnapshot


# ---------------------------------------------------------------------------
# Stub Alpaca client
# ---------------------------------------------------------------------------


class StubAlpacaClient:
    """Minimal stub that replaces AlpacaApiClient for unit tests."""

    def __init__(
        self,
        bars: dict[str, FirstMinuteBar] | None = None,
        fail_symbol: str | None = None,
    ) -> None:
        self._bars = bars or {}
        self._fail_symbol = fail_symbol

    async def get_first_minute_bar(
        self, symbol: str, trade_date: date | None = None
    ) -> FirstMinuteBar:
        if self._fail_symbol == symbol:
            raise AlpacaApiError(f"stubbed failure for {symbol}")
        if symbol in self._bars:
            return self._bars[symbol]
        raise AlpacaApiError(f"no bar for {symbol}")

    # Satisfy enough of AlpacaApiClient's interface for DashboardService.
    def get_quote(self, *_: object) -> None:  # pragma: no cover
        ...


def _make_bar(
    symbol: str = "AAPL",
    open: float = 150.0,
    high: float = 152.0,
    low: float = 149.0,
    close: float = 151.0,
    volume: float = 3_000_000.0,
) -> FirstMinuteBar:
    return FirstMinuteBar(
        symbol=symbol,
        bar_time="2026-03-30T13:30:00Z",
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _make_service(
    alpaca: StubAlpacaClient,
    tickers: tuple[str, ...] = ("AAPL",),
    option_strikes: tuple[str, ...] = (),
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> DashboardService:
    """Build a DashboardService with a stub neo client and stub Alpaca client."""
    from unittest.mock import MagicMock

    stub_neo = MagicMock()
    svc = DashboardService(neo=stub_neo, alpaca=alpaca)  # type: ignore[arg-type]
    if monkeypatch is not None:
        monkeypatch.setattr("fluxid.service.settings.opening_bar_tickers", tickers)
        monkeypatch.setattr("fluxid.service.settings.opening_bar_option_strikes", option_strikes)
    return svc


# ---------------------------------------------------------------------------
# load_opening_bar_data — happy path
# ---------------------------------------------------------------------------


def test_load_opening_bar_data_returns_snapshot_per_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(bars={"AAPL": _make_bar("AAPL"), "SPY": _make_bar("SPY")})
    svc = _make_service(alpaca, tickers=("AAPL", "SPY"), monkeypatch=monkeypatch)

    snapshots = asyncio.run(svc.load_opening_bar_data())

    assert len(snapshots) == 2
    assert snapshots[0].symbol == "AAPL"
    assert snapshots[1].symbol == "SPY"


def test_load_opening_bar_data_ohlc_values(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(bars={"AAPL": _make_bar("AAPL", open=150.0, high=152.0, low=149.0, close=151.0)})
    svc = _make_service(alpaca, tickers=("AAPL",), monkeypatch=monkeypatch)

    (snap,) = asyncio.run(svc.load_opening_bar_data())

    assert snap.open == 150.0
    assert snap.high == 152.0
    assert snap.low == 149.0
    assert snap.close == 151.0
    assert snap.error == ""


def test_load_opening_bar_data_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(bars={"AAPL": _make_bar("AAPL", volume=5_000_000.0)})
    svc = _make_service(alpaca, tickers=("AAPL",), monkeypatch=monkeypatch)

    (snap,) = asyncio.run(svc.load_opening_bar_data())

    assert snap.volume == 5_000_000.0


def test_load_opening_bar_data_bar_time(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(bars={"AAPL": _make_bar("AAPL")})
    svc = _make_service(alpaca, tickers=("AAPL",), monkeypatch=monkeypatch)

    (snap,) = asyncio.run(svc.load_opening_bar_data())

    assert snap.bar_time == "2026-03-30T13:30:00Z"


def test_load_opening_bar_data_display_name_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(bars={"AAPL": _make_bar("AAPL")})
    svc = _make_service(alpaca, tickers=("AAPL",), monkeypatch=monkeypatch)

    (snap,) = asyncio.run(svc.load_opening_bar_data())

    assert snap.display_name == "Apple"


def test_load_opening_bar_data_unknown_symbol_uses_symbol_as_name(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(bars={"XYZ": _make_bar("XYZ")})
    svc = _make_service(alpaca, tickers=("XYZ",), monkeypatch=monkeypatch)

    (snap,) = asyncio.run(svc.load_opening_bar_data())

    assert snap.display_name == "XYZ"


# ---------------------------------------------------------------------------
# load_opening_bar_data — option strikes merged in
# ---------------------------------------------------------------------------


def test_load_opening_bar_data_includes_option_strikes(monkeypatch: pytest.MonkeyPatch) -> None:
    opt_sym = "AAPL260117C00200000"
    alpaca = StubAlpacaClient(bars={"AAPL": _make_bar("AAPL"), opt_sym: _make_bar(opt_sym)})
    svc = _make_service(
        alpaca,
        tickers=("AAPL",),
        option_strikes=(opt_sym,),
        monkeypatch=monkeypatch,
    )

    snapshots = asyncio.run(svc.load_opening_bar_data())

    symbols = [s.symbol for s in snapshots]
    assert "AAPL" in symbols
    assert opt_sym in symbols


# ---------------------------------------------------------------------------
# load_opening_bar_data — error handling
# ---------------------------------------------------------------------------


def test_load_opening_bar_data_error_captured_per_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(
        bars={"SPY": _make_bar("SPY")},
        fail_symbol="AAPL",
    )
    svc = _make_service(alpaca, tickers=("AAPL", "SPY"), monkeypatch=monkeypatch)

    snapshots = asyncio.run(svc.load_opening_bar_data())

    aapl = next(s for s in snapshots if s.symbol == "AAPL")
    spy = next(s for s in snapshots if s.symbol == "SPY")

    assert "stubbed failure for AAPL" in aapl.error
    assert aapl.open is None
    assert spy.error == ""
    assert spy.open == 150.0


def test_load_opening_bar_data_error_snapshot_all_none(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient(fail_symbol="AAPL")
    svc = _make_service(alpaca, tickers=("AAPL",), monkeypatch=monkeypatch)

    (snap,) = asyncio.run(svc.load_opening_bar_data())

    assert snap.open is None
    assert snap.high is None
    assert snap.low is None
    assert snap.close is None
    assert snap.volume is None
    assert snap.bar_time is None


# ---------------------------------------------------------------------------
# load_opening_bar_data — no Alpaca client / empty config
# ---------------------------------------------------------------------------


def test_load_opening_bar_data_returns_empty_when_no_alpaca_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    stub_neo = MagicMock()
    svc = DashboardService(neo=stub_neo, alpaca=None)  # type: ignore[arg-type]
    monkeypatch.setattr("fluxid.service.settings.opening_bar_tickers", ("AAPL",))
    monkeypatch.setattr("fluxid.service.settings.opening_bar_option_strikes", ())

    snapshots = asyncio.run(svc.load_opening_bar_data())

    assert snapshots == []


def test_load_opening_bar_data_returns_empty_when_no_tickers(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca = StubAlpacaClient()
    svc = _make_service(alpaca, tickers=(), option_strikes=(), monkeypatch=monkeypatch)

    snapshots = asyncio.run(svc.load_opening_bar_data())

    assert snapshots == []


# ---------------------------------------------------------------------------
# OpeningBarSnapshot dataclass
# ---------------------------------------------------------------------------


def test_opening_bar_snapshot_is_dataclass() -> None:
    snap = OpeningBarSnapshot(
        symbol="AAPL",
        display_name="Apple",
        bar_time="2026-03-30T13:30:00Z",
        open=150.0,
        high=152.0,
        low=149.0,
        close=151.0,
        volume=3_000_000.0,
    )
    assert snap.symbol == "AAPL"
    assert snap.error == ""


def test_opening_bar_snapshot_error_field_defaults_empty() -> None:
    snap = OpeningBarSnapshot(
        symbol="SPY",
        display_name="SPDR S&P 500 ETF",
        bar_time=None,
        open=None,
        high=None,
        low=None,
        close=None,
        volume=None,
    )
    assert snap.error == ""
