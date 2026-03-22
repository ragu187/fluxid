"""Tests for service-layer view-model helpers introduced in Phase 2."""
from __future__ import annotations

import pytest

from fluxid.neo_client import MarketQuote
from fluxid.service import (
    OptionChainOHLCRow,
    OptionStrikeRow,
    _parse_option_symbol,
    _strike_moneyness,
    build_option_chain_ohlc_rows,
    build_strike_rows,
)


# ---------------------------------------------------------------------------
# _parse_option_symbol
# ---------------------------------------------------------------------------


def test_parse_option_symbol_ce() -> None:
    assert _parse_option_symbol("NIFTY_24000_CE") == (24000, "CE")


def test_parse_option_symbol_pe() -> None:
    assert _parse_option_symbol("NIFTY_24000_PE") == (24000, "PE")


def test_parse_option_symbol_banknifty() -> None:
    assert _parse_option_symbol("BANKNIFTY_50000_CE") == (50000, "CE")


def test_parse_option_symbol_non_option_returns_none() -> None:
    assert _parse_option_symbol("NIFTY_SPOT") is None


def test_parse_option_symbol_futures_returns_none() -> None:
    assert _parse_option_symbol("NIFTY_FUT") is None


def test_parse_option_symbol_unknown_side_returns_none() -> None:
    # "XX" is not a recognised option side
    assert _parse_option_symbol("NIFTY_24000_XX") is None


def test_parse_option_symbol_non_numeric_strike_returns_none() -> None:
    assert _parse_option_symbol("NIFTY_ABC_CE") is None


def test_parse_option_symbol_empty_returns_none() -> None:
    assert _parse_option_symbol("") is None


# ---------------------------------------------------------------------------
# _strike_moneyness
# ---------------------------------------------------------------------------


def test_strike_moneyness_atm() -> None:
    assert _strike_moneyness(24000, 24000) == "ATM"


def test_strike_moneyness_itm() -> None:
    # Strike below ATM → ITM for CE
    assert _strike_moneyness(23950, 24000) == "ITM"


def test_strike_moneyness_otm() -> None:
    # Strike above ATM → OTM for CE
    assert _strike_moneyness(24050, 24000) == "OTM"


# ---------------------------------------------------------------------------
# build_strike_rows
# ---------------------------------------------------------------------------


def _make_quote(symbol: str, ltp: float = 100.0) -> MarketQuote:
    return MarketQuote(symbol=symbol, ltp=ltp, change=1.5, pct_change=1.5, volume=5000)


def test_build_strike_rows_basic_grouping() -> None:
    quotes = [
        _make_quote("NIFTY_24000_CE"),
        _make_quote("NIFTY_24000_PE"),
        _make_quote("NIFTY_24050_CE"),
        _make_quote("NIFTY_24050_PE"),
    ]
    rows = build_strike_rows(quotes, atm_strike=24000)
    assert len(rows) == 2
    assert rows[0].strike == 24000
    assert rows[1].strike == 24050


def test_build_strike_rows_ce_and_pe_paired() -> None:
    quotes = [
        _make_quote("NIFTY_24000_CE", ltp=120.0),
        _make_quote("NIFTY_24000_PE", ltp=80.0),
    ]
    rows = build_strike_rows(quotes, atm_strike=24000)
    assert rows[0].ce is not None
    assert rows[0].pe is not None
    assert rows[0].ce.ltp == 120.0
    assert rows[0].pe.ltp == 80.0


def test_build_strike_rows_atm_flagged() -> None:
    quotes = [
        _make_quote("NIFTY_23950_CE"),
        _make_quote("NIFTY_23950_PE"),
        _make_quote("NIFTY_24000_CE"),
        _make_quote("NIFTY_24000_PE"),
        _make_quote("NIFTY_24050_CE"),
        _make_quote("NIFTY_24050_PE"),
    ]
    rows = build_strike_rows(quotes, atm_strike=24000)
    atm_rows = [r for r in rows if r.is_atm]
    assert len(atm_rows) == 1
    assert atm_rows[0].strike == 24000


def test_build_strike_rows_moneyness_values() -> None:
    quotes = [
        _make_quote("NIFTY_23950_CE"),
        _make_quote("NIFTY_23950_PE"),
        _make_quote("NIFTY_24000_CE"),
        _make_quote("NIFTY_24000_PE"),
        _make_quote("NIFTY_24050_CE"),
        _make_quote("NIFTY_24050_PE"),
    ]
    rows = build_strike_rows(quotes, atm_strike=24000)
    by_strike = {r.strike: r for r in rows}
    assert by_strike[23950].moneyness == "ITM"
    assert by_strike[24000].moneyness == "ATM"
    assert by_strike[24050].moneyness == "OTM"


def test_build_strike_rows_ascending_order() -> None:
    quotes = [
        _make_quote("NIFTY_24050_CE"),
        _make_quote("NIFTY_23950_CE"),
        _make_quote("NIFTY_24000_CE"),
    ]
    rows = build_strike_rows(quotes, atm_strike=24000)
    strikes = [r.strike for r in rows]
    assert strikes == sorted(strikes)


def test_build_strike_rows_missing_pe_is_none() -> None:
    quotes = [_make_quote("NIFTY_24000_CE")]
    rows = build_strike_rows(quotes, atm_strike=24000)
    assert rows[0].ce is not None
    assert rows[0].pe is None


def test_build_strike_rows_missing_ce_is_none() -> None:
    quotes = [_make_quote("NIFTY_24000_PE")]
    rows = build_strike_rows(quotes, atm_strike=24000)
    assert rows[0].ce is None
    assert rows[0].pe is not None


def test_build_strike_rows_empty_quotes() -> None:
    rows = build_strike_rows([], atm_strike=24000)
    assert rows == []


def test_build_strike_rows_ignores_non_option_symbols() -> None:
    quotes = [
        _make_quote("NIFTY_SPOT"),
        _make_quote("NIFTY_FUT"),
        _make_quote("NIFTY_24000_CE"),
    ]
    rows = build_strike_rows(quotes, atm_strike=24000)
    assert len(rows) == 1
    assert rows[0].strike == 24000


def test_build_strike_rows_returns_option_strike_row_instances() -> None:
    quotes = [_make_quote("NIFTY_24000_CE"), _make_quote("NIFTY_24000_PE")]
    rows = build_strike_rows(quotes, atm_strike=24000)
    for row in rows:
        assert isinstance(row, OptionStrikeRow)


# ---------------------------------------------------------------------------
# build_option_chain_ohlc_rows
# ---------------------------------------------------------------------------


def _make_ohlc_quote(
    symbol: str,
    ltp: float = 100.0,
    open: float | None = None,
    high: float | None = None,
    low: float | None = None,
) -> MarketQuote:
    return MarketQuote(symbol=symbol, ltp=ltp, open=open, high=high, low=low)


def test_build_option_chain_ohlc_rows_basic_pairing() -> None:
    quotes = [
        _make_ohlc_quote("NIFTY_24000_CE", open=110.0, high=130.0, low=90.0),
        _make_ohlc_quote("NIFTY_24000_PE", open=80.0, high=95.0, low=70.0),
    ]
    rows = build_option_chain_ohlc_rows(quotes)
    assert len(rows) == 1
    row = rows[0]
    assert row.strike == 24000
    assert row.ce_symbol == "NIFTY_24000_CE"
    assert row.ce_open == 110.0
    assert row.ce_high == 130.0
    assert row.ce_low == 90.0
    assert row.pe_symbol == "NIFTY_24000_PE"
    assert row.pe_open == 80.0
    assert row.pe_high == 95.0
    assert row.pe_low == 70.0


def test_build_option_chain_ohlc_rows_ascending_strike_order() -> None:
    quotes = [
        _make_ohlc_quote("NIFTY_24050_CE"),
        _make_ohlc_quote("NIFTY_23950_CE"),
        _make_ohlc_quote("NIFTY_24000_CE"),
    ]
    rows = build_option_chain_ohlc_rows(quotes)
    strikes = [r.strike for r in rows]
    assert strikes == sorted(strikes)


def test_build_option_chain_ohlc_rows_missing_ce_gives_none_fields() -> None:
    quotes = [_make_ohlc_quote("NIFTY_24000_PE", open=80.0, high=95.0, low=70.0)]
    rows = build_option_chain_ohlc_rows(quotes)
    assert len(rows) == 1
    row = rows[0]
    assert row.ce_symbol is None
    assert row.ce_open is None
    assert row.ce_high is None
    assert row.ce_low is None


def test_build_option_chain_ohlc_rows_missing_pe_gives_none_fields() -> None:
    quotes = [_make_ohlc_quote("NIFTY_24000_CE", open=110.0, high=130.0, low=90.0)]
    rows = build_option_chain_ohlc_rows(quotes)
    assert len(rows) == 1
    row = rows[0]
    assert row.pe_symbol is None
    assert row.pe_open is None
    assert row.pe_high is None
    assert row.pe_low is None


def test_build_option_chain_ohlc_rows_ohlc_none_when_not_in_quote() -> None:
    quotes = [
        _make_ohlc_quote("NIFTY_24000_CE"),  # open/high/low all None
        _make_ohlc_quote("NIFTY_24000_PE"),
    ]
    rows = build_option_chain_ohlc_rows(quotes)
    row = rows[0]
    assert row.ce_open is None
    assert row.ce_high is None
    assert row.ce_low is None


def test_build_option_chain_ohlc_rows_multiple_strikes() -> None:
    quotes = [
        _make_ohlc_quote("NIFTY_24000_CE"),
        _make_ohlc_quote("NIFTY_24000_PE"),
        _make_ohlc_quote("NIFTY_24050_CE"),
        _make_ohlc_quote("NIFTY_24050_PE"),
    ]
    rows = build_option_chain_ohlc_rows(quotes)
    assert len(rows) == 2
    assert rows[0].strike == 24000
    assert rows[1].strike == 24050


def test_build_option_chain_ohlc_rows_empty_quotes() -> None:
    rows = build_option_chain_ohlc_rows([])
    assert rows == []


def test_build_option_chain_ohlc_rows_ignores_non_option_symbols() -> None:
    quotes = [
        _make_ohlc_quote("NIFTY_SPOT"),
        _make_ohlc_quote("NIFTY_FUT"),
        _make_ohlc_quote("NIFTY_24000_CE", open=100.0, high=120.0, low=80.0),
    ]
    rows = build_option_chain_ohlc_rows(quotes)
    assert len(rows) == 1
    assert rows[0].strike == 24000


def test_build_option_chain_ohlc_rows_returns_ohlc_row_instances() -> None:
    quotes = [
        _make_ohlc_quote("NIFTY_24000_CE"),
        _make_ohlc_quote("NIFTY_24000_PE"),
    ]
    rows = build_option_chain_ohlc_rows(quotes)
    for row in rows:
        assert isinstance(row, OptionChainOHLCRow)
