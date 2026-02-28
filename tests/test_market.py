from datetime import datetime

from fluxid.market import expand_generic_symbols, is_market_day, nearest_strike, option_strikes


def test_is_market_day_weekday() -> None:
    assert is_market_day(datetime(2026, 1, 5)) is True  # Monday


def test_is_market_day_weekend() -> None:
    assert is_market_day(datetime(2026, 1, 4)) is False  # Sunday


def test_option_strikes_atm_plus_minus_five() -> None:
    strikes = option_strikes(atm=24000, step=50, depth=5)
    assert strikes[0] == 23750
    assert strikes[-1] == 24250
    assert len(strikes) == 11


def test_expand_generic_symbols() -> None:
    symbols = list(expand_generic_symbols("NIFTY", 24112, step=50, depth=1))
    assert symbols == [
        "NIFTY_24050_CE",
        "NIFTY_24050_PE",
        "NIFTY_24100_CE",
        "NIFTY_24100_PE",
        "NIFTY_24150_CE",
        "NIFTY_24150_PE",
    ]


def test_nearest_strike_rounding() -> None:
    assert nearest_strike(24126, 50) == 24150
