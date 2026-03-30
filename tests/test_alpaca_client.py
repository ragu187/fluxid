"""Tests for AlpacaApiClient snapshot parsing."""
from __future__ import annotations

from typing import Any

import pytest

from fluxid.alpaca_client import AlpacaApiClient, AlpacaApiError
from fluxid.neo_client import MarketQuote


# Minimal client – credentials are unused in unit tests that call _coerce_snapshot directly.
_client = AlpacaApiClient(
    base_url="https://data.alpaca.markets",
    key_id="test-key",
    secret_key="test-secret",
)


def _make_snap(
    trade_price: float | None = 150.0,
    prev_close: float | None = 148.0,
    open_: float | None = 149.0,
    high: float | None = 151.5,
    low: float | None = 148.5,
    volume: float | None = 50_000_000.0,
) -> dict[str, Any]:
    snap: dict[str, Any] = {}
    if trade_price is not None:
        snap["latestTrade"] = {"p": trade_price, "s": 100, "x": "Q"}
    if any(v is not None for v in (open_, high, low, volume)):
        snap["dailyBar"] = {
            "o": open_,
            "h": high,
            "l": low,
            "v": volume,
            "c": trade_price,
        }
    if prev_close is not None:
        snap["prevDailyBar"] = {"c": prev_close}
    return snap


def _coerce(snap: dict[str, Any], symbol: str = "AAPL") -> MarketQuote:
    return _client._coerce_snapshot(symbol=symbol, snap=snap)


# ---------------------------------------------------------------------------
# LTP (last trade price)
# ---------------------------------------------------------------------------


def test_coerce_ltp_from_latest_trade() -> None:
    quote = _coerce(_make_snap(trade_price=153.25))
    assert quote.ltp == 153.25


def test_coerce_missing_ltp_raises() -> None:
    snap = {"latestTrade": {}}  # 'p' field absent
    with pytest.raises(AlpacaApiError, match="missing trade price"):
        _coerce(snap)


def test_coerce_missing_latest_trade_raises() -> None:
    snap = {}  # no latestTrade at all
    with pytest.raises(AlpacaApiError, match="missing trade price"):
        _coerce(snap)


# ---------------------------------------------------------------------------
# OHLC fields
# ---------------------------------------------------------------------------


def test_coerce_open() -> None:
    quote = _coerce(_make_snap(open_=149.0))
    assert quote.open == 149.0


def test_coerce_high() -> None:
    quote = _coerce(_make_snap(high=155.0))
    assert quote.high == 155.0


def test_coerce_low() -> None:
    quote = _coerce(_make_snap(low=147.0))
    assert quote.low == 147.0


def test_coerce_volume() -> None:
    quote = _coerce(_make_snap(volume=80_000_000.0))
    assert quote.volume == 80_000_000.0


def test_coerce_ohlc_none_when_daily_bar_absent() -> None:
    snap = {"latestTrade": {"p": 100.0}}
    quote = _coerce(snap)
    assert quote.open is None
    assert quote.high is None
    assert quote.low is None
    assert quote.volume is None


def test_coerce_ohlc_none_when_daily_bar_fields_are_none() -> None:
    snap = {
        "latestTrade": {"p": 100.0},
        "dailyBar": {"o": None, "h": None, "l": None, "v": None, "c": 100.0},
    }
    quote = _coerce(snap)
    assert quote.open is None
    assert quote.high is None
    assert quote.low is None
    assert quote.volume is None


# ---------------------------------------------------------------------------
# Change / pct_change calculations
# ---------------------------------------------------------------------------


def test_coerce_change_computed_from_prev_close() -> None:
    quote = _coerce(_make_snap(trade_price=150.0, prev_close=148.0))
    assert quote.change == pytest.approx(2.0)


def test_coerce_pct_change_computed_from_prev_close() -> None:
    quote = _coerce(_make_snap(trade_price=150.0, prev_close=148.0))
    assert quote.pct_change == pytest.approx((2.0 / 148.0) * 100)


def test_coerce_change_none_when_prev_close_absent() -> None:
    snap = _make_snap(trade_price=150.0)
    snap.pop("prevDailyBar", None)
    quote = _coerce(snap)
    assert quote.change is None
    assert quote.pct_change is None


def test_coerce_change_none_when_prev_close_zero() -> None:
    snap = _make_snap(trade_price=150.0, prev_close=0.0)
    quote = _coerce(snap)
    assert quote.change is None
    assert quote.pct_change is None


# ---------------------------------------------------------------------------
# Symbol preserved in result
# ---------------------------------------------------------------------------


def test_coerce_symbol_preserved() -> None:
    quote = _coerce(_make_snap(), symbol="SPY")
    assert quote.symbol == "SPY"


# ---------------------------------------------------------------------------
# Source payload stored
# ---------------------------------------------------------------------------


def test_coerce_source_payload_stored() -> None:
    snap = _make_snap()
    quote = _coerce(snap)
    assert quote.source_payload is snap


# ---------------------------------------------------------------------------
# Non-numeric values silently coerce to None
# ---------------------------------------------------------------------------


def test_coerce_non_numeric_open_is_none() -> None:
    snap = _make_snap()
    snap["dailyBar"]["o"] = "N/A"
    quote = _coerce(snap)
    assert quote.open is None


def test_coerce_non_numeric_high_is_none() -> None:
    snap = _make_snap()
    snap["dailyBar"]["h"] = "-"
    quote = _coerce(snap)
    assert quote.high is None


# ---------------------------------------------------------------------------
# AlpacaQuoteProvider implements QuoteProvider protocol
# ---------------------------------------------------------------------------


def test_alpaca_quote_provider_satisfies_protocol() -> None:
    from fluxid.alpaca_client import AlpacaQuoteProvider
    from fluxid.neo_client import QuoteProvider

    provider = AlpacaQuoteProvider(_client)
    assert isinstance(provider, QuoteProvider)


# ---------------------------------------------------------------------------
# FirstMinuteBar / _coerce_bar
# ---------------------------------------------------------------------------


def _make_bar(
    t: str = "2026-03-30T13:30:00Z",
    o: float | None = 150.0,
    h: float | None = 152.5,
    l: float | None = 149.0,
    c: float | None = 151.0,
    v: float | None = 3_000_000.0,
) -> dict[str, Any]:
    bar: dict[str, Any] = {"t": t}
    if o is not None:
        bar["o"] = o
    if h is not None:
        bar["h"] = h
    if l is not None:
        bar["l"] = l
    if c is not None:
        bar["c"] = c
    if v is not None:
        bar["v"] = v
    return bar


def _coerce_bar(bar: dict[str, Any], symbol: str = "AAPL") -> "FirstMinuteBar":
    from fluxid.alpaca_client import FirstMinuteBar  # noqa: F401
    return _client._coerce_bar(symbol=symbol, bar=bar)


def test_coerce_bar_ohlc_fields() -> None:
    bar = _coerce_bar(_make_bar(o=150.0, h=152.5, l=149.0, c=151.0))
    assert bar.open == 150.0
    assert bar.high == 152.5
    assert bar.low == 149.0
    assert bar.close == 151.0


def test_coerce_bar_volume() -> None:
    bar = _coerce_bar(_make_bar(v=5_000_000.0))
    assert bar.volume == 5_000_000.0


def test_coerce_bar_volume_none_when_absent() -> None:
    raw = _make_bar()
    raw.pop("v", None)
    bar = _coerce_bar(raw)
    assert bar.volume is None


def test_coerce_bar_symbol_preserved() -> None:
    bar = _coerce_bar(_make_bar(), symbol="SPY")
    assert bar.symbol == "SPY"


def test_coerce_bar_timestamp_preserved() -> None:
    ts = "2026-03-30T13:30:00Z"
    bar = _coerce_bar(_make_bar(t=ts))
    assert bar.bar_time == ts


def test_coerce_bar_missing_open_raises() -> None:
    from fluxid.alpaca_client import AlpacaApiError

    raw = _make_bar()
    raw.pop("o")
    with pytest.raises(AlpacaApiError, match="missing required OHLC"):
        _coerce_bar(raw)


def test_coerce_bar_missing_close_raises() -> None:
    from fluxid.alpaca_client import AlpacaApiError

    raw = _make_bar()
    raw.pop("c")
    with pytest.raises(AlpacaApiError, match="missing required OHLC"):
        _coerce_bar(raw)


def test_coerce_bar_returns_first_minute_bar_instance() -> None:
    from fluxid.alpaca_client import FirstMinuteBar

    bar = _coerce_bar(_make_bar())
    assert isinstance(bar, FirstMinuteBar)

