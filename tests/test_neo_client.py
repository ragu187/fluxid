"""Tests for NeoApiClient OHLC parsing added to _coerce_quote()."""
from __future__ import annotations

import pytest

from fluxid.neo_client import MarketQuote, NeoApiClient, NeoApiError


# Minimal client – credentials are unused in unit tests that call _coerce_quote directly.
_client = NeoApiClient(base_url="http://localhost", api_key="test")


def _coerce(payload: dict) -> MarketQuote:
    return _client._coerce_quote(symbol="NIFTY_24000_CE", payload=payload)


# ---------------------------------------------------------------------------
# LTP variants (existing behaviour must remain)
# ---------------------------------------------------------------------------


def test_coerce_quote_ltp_field() -> None:
    quote = _coerce({"ltp": 100.5})
    assert quote.ltp == 100.5


def test_coerce_quote_last_price_fallback() -> None:
    quote = _coerce({"last_price": 200.0})
    assert quote.ltp == 200.0


def test_coerce_quote_missing_ltp_raises() -> None:
    with pytest.raises(NeoApiError):
        _coerce({})


# ---------------------------------------------------------------------------
# OHLC – primary field names
# ---------------------------------------------------------------------------


def test_coerce_quote_open_field() -> None:
    quote = _coerce({"ltp": 100.0, "open": 98.0})
    assert quote.open == 98.0


def test_coerce_quote_high_field() -> None:
    quote = _coerce({"ltp": 100.0, "high": 115.0})
    assert quote.high == 115.0


def test_coerce_quote_low_field() -> None:
    quote = _coerce({"ltp": 100.0, "low": 90.0})
    assert quote.low == 90.0


# ---------------------------------------------------------------------------
# OHLC – alternate field names (camelCase / day-prefix)
# ---------------------------------------------------------------------------


def test_coerce_quote_openPrice_fallback() -> None:
    quote = _coerce({"ltp": 100.0, "openPrice": 97.0})
    assert quote.open == 97.0


def test_coerce_quote_highPrice_fallback() -> None:
    quote = _coerce({"ltp": 100.0, "highPrice": 120.0})
    assert quote.high == 120.0


def test_coerce_quote_lowPrice_fallback() -> None:
    quote = _coerce({"ltp": 100.0, "lowPrice": 88.0})
    assert quote.low == 88.0


def test_coerce_quote_dayOpen_fallback() -> None:
    quote = _coerce({"ltp": 100.0, "dayOpen": 96.0})
    assert quote.open == 96.0


def test_coerce_quote_dayHigh_fallback() -> None:
    quote = _coerce({"ltp": 100.0, "dayHigh": 118.0})
    assert quote.high == 118.0


def test_coerce_quote_dayLow_fallback() -> None:
    quote = _coerce({"ltp": 100.0, "dayLow": 85.0})
    assert quote.low == 85.0


# ---------------------------------------------------------------------------
# OHLC – missing fields default to None (backward-compatible)
# ---------------------------------------------------------------------------


def test_coerce_quote_open_none_when_absent() -> None:
    quote = _coerce({"ltp": 100.0})
    assert quote.open is None


def test_coerce_quote_high_none_when_absent() -> None:
    quote = _coerce({"ltp": 100.0})
    assert quote.high is None


def test_coerce_quote_low_none_when_absent() -> None:
    quote = _coerce({"ltp": 100.0})
    assert quote.low is None


# ---------------------------------------------------------------------------
# OHLC – data wrapper (payload with nested "data" key)
# ---------------------------------------------------------------------------


def test_coerce_quote_ohlc_inside_data_key() -> None:
    payload = {"data": {"ltp": 100.0, "open": 95.0, "high": 112.0, "low": 88.0}}
    quote = _coerce(payload)
    assert quote.ltp == 100.0
    assert quote.open == 95.0
    assert quote.high == 112.0
    assert quote.low == 88.0


# ---------------------------------------------------------------------------
# OHLC – non-numeric values are silently coerced to None
# ---------------------------------------------------------------------------


def test_coerce_quote_non_numeric_open_is_none() -> None:
    quote = _coerce({"ltp": 100.0, "open": "N/A"})
    assert quote.open is None


def test_coerce_quote_non_numeric_high_is_none() -> None:
    quote = _coerce({"ltp": 100.0, "high": "-"})
    assert quote.high is None


def test_coerce_quote_non_numeric_low_is_none() -> None:
    quote = _coerce({"ltp": 100.0, "low": None})
    assert quote.low is None
