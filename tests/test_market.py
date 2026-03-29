from datetime import datetime, timezone, timedelta

import pytest
from zoneinfo import ZoneInfo

from fluxid.market import (
    EXCHANGE_TZ,
    expand_generic_symbols,
    is_market_day,
    is_market_day_india,
    is_market_day_us,
    is_market_open_india,
    is_market_open_us,
    is_us_market_day,
    nearest_strike,
    option_strikes,
)


# ---------------------------------------------------------------------------
# is_market_day – basic weekday / weekend
# ---------------------------------------------------------------------------

def test_is_market_day_weekday() -> None:
    assert is_market_day(datetime(2026, 1, 5)) is True  # Monday


def test_is_market_day_weekend() -> None:
    assert is_market_day(datetime(2026, 1, 4)) is False  # Sunday


def test_is_market_day_saturday() -> None:
    assert is_market_day(datetime(2026, 1, 3)) is False  # Saturday


def test_is_market_day_friday() -> None:
    assert is_market_day(datetime(2026, 1, 2)) is True  # Friday


# ---------------------------------------------------------------------------
# is_market_day – timezone-aware datetime handling
# ---------------------------------------------------------------------------

def test_is_market_day_aware_weekday() -> None:
    # 2026-01-05 Monday 10:00 IST (UTC+5:30)
    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 1, 5, 10, 0, tzinfo=ist)
    assert is_market_day(dt) is True


def test_is_market_day_aware_weekend() -> None:
    # 2026-01-04 Sunday in IST
    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 1, 4, 10, 0, tzinfo=ist)
    assert is_market_day(dt) is False


def test_is_market_day_utc_sunday_converts_to_ist_monday() -> None:
    # Sunday 22:00 UTC == Monday 03:30 IST → weekday in exchange tz
    dt = datetime(2026, 1, 4, 22, 0, tzinfo=timezone.utc)
    assert is_market_day(dt) is True


def test_is_market_day_utc_monday_converts_to_ist_still_monday() -> None:
    # Monday 00:00 UTC == Monday 05:30 IST
    dt = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    assert is_market_day(dt) is True


def test_is_market_day_aware_uses_exchange_tz_not_utc_offset() -> None:
    # Provide time in UTC+0; function must convert to IST for the weekday check.
    dt_utc = datetime(2026, 1, 4, 22, 30, tzinfo=timezone.utc)
    dt_ist = dt_utc.astimezone(EXCHANGE_TZ)
    # Both calls must agree after conversion to IST
    assert is_market_day(dt_utc) == is_market_day(dt_ist)


def test_is_market_day_no_arg_returns_bool() -> None:
    # Smoke test: calling without argument must not raise and return a bool.
    result = is_market_day()
    assert isinstance(result, bool)


def test_is_us_market_day_weekday() -> None:
    assert is_us_market_day(datetime(2026, 1, 5)) is True


def test_is_us_market_day_weekend() -> None:
    assert is_us_market_day(datetime(2026, 1, 4)) is False


# ---------------------------------------------------------------------------
# is_market_day_india / is_market_day_us – alias coverage
# ---------------------------------------------------------------------------

def test_is_market_day_india_weekday() -> None:
    assert is_market_day_india(datetime(2026, 1, 5)) is True


def test_is_market_day_india_weekend() -> None:
    assert is_market_day_india(datetime(2026, 1, 4)) is False


def test_is_market_day_us_weekday() -> None:
    assert is_market_day_us(datetime(2026, 1, 5)) is True


def test_is_market_day_us_weekend() -> None:
    assert is_market_day_us(datetime(2026, 1, 4)) is False


# ---------------------------------------------------------------------------
# is_market_open_india – session hours (09:15–15:30 IST, weekdays)
# ---------------------------------------------------------------------------

def test_is_market_open_india_during_session() -> None:
    # Wednesday 2026-01-07 12:00 IST (weekday, within session)
    dt = datetime(2026, 1, 7, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open_india(dt) is True


def test_is_market_open_india_before_session() -> None:
    # Wednesday 2026-01-07 08:00 IST (before 09:15)
    dt = datetime(2026, 1, 7, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open_india(dt) is False


def test_is_market_open_india_after_session() -> None:
    # Wednesday 2026-01-07 16:00 IST (after 15:30)
    dt = datetime(2026, 1, 7, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open_india(dt) is False


def test_is_market_open_india_at_open() -> None:
    # Exactly at 09:15 IST – boundary is inclusive
    dt = datetime(2026, 1, 7, 9, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open_india(dt) is True


def test_is_market_open_india_at_close() -> None:
    # Exactly at 15:30 IST – boundary is inclusive
    dt = datetime(2026, 1, 7, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open_india(dt) is True


def test_is_market_open_india_on_weekend() -> None:
    # Saturday 2026-01-10 12:00 IST
    dt = datetime(2026, 1, 10, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open_india(dt) is False


def test_is_market_open_india_no_arg_returns_bool() -> None:
    result = is_market_open_india()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# is_market_open_us – session hours (09:30–16:00 ET, weekdays)
# ---------------------------------------------------------------------------

def test_is_market_open_us_during_session() -> None:
    # Wednesday 2026-01-07 13:00 ET (weekday, within session)
    et = ZoneInfo("America/New_York")
    dt = datetime(2026, 1, 7, 13, 0, tzinfo=et)
    assert is_market_open_us(dt) is True


def test_is_market_open_us_before_session() -> None:
    # Wednesday 2026-01-07 08:00 ET (before 09:30)
    et = ZoneInfo("America/New_York")
    dt = datetime(2026, 1, 7, 8, 0, tzinfo=et)
    assert is_market_open_us(dt) is False


def test_is_market_open_us_after_session() -> None:
    # Wednesday 2026-01-07 17:00 ET (after 16:00)
    et = ZoneInfo("America/New_York")
    dt = datetime(2026, 1, 7, 17, 0, tzinfo=et)
    assert is_market_open_us(dt) is False


def test_is_market_open_us_at_open() -> None:
    # Exactly at 09:30 ET – boundary is inclusive
    et = ZoneInfo("America/New_York")
    dt = datetime(2026, 1, 7, 9, 30, tzinfo=et)
    assert is_market_open_us(dt) is True


def test_is_market_open_us_at_close() -> None:
    # Exactly at 16:00 ET – boundary is inclusive
    et = ZoneInfo("America/New_York")
    dt = datetime(2026, 1, 7, 16, 0, tzinfo=et)
    assert is_market_open_us(dt) is True


def test_is_market_open_us_on_weekend() -> None:
    # Saturday 2026-01-10 13:00 ET
    et = ZoneInfo("America/New_York")
    dt = datetime(2026, 1, 10, 13, 0, tzinfo=et)
    assert is_market_open_us(dt) is False


def test_is_market_open_us_no_arg_returns_bool() -> None:
    result = is_market_open_us()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# nearest_strike – rounding and validation
# ---------------------------------------------------------------------------

def test_nearest_strike_rounding() -> None:
    assert nearest_strike(24126, 50) == 24150


def test_nearest_strike_exact() -> None:
    assert nearest_strike(24100, 50) == 24100


def test_nearest_strike_round_down() -> None:
    assert nearest_strike(24124, 50) == 24100


def test_nearest_strike_zero_step_raises() -> None:
    with pytest.raises(ValueError, match="step"):
        nearest_strike(24000, 0)


def test_nearest_strike_negative_step_raises() -> None:
    with pytest.raises(ValueError, match="step"):
        nearest_strike(24000, -50)


# ---------------------------------------------------------------------------
# option_strikes – validation and output
# ---------------------------------------------------------------------------

def test_option_strikes_atm_plus_minus_five() -> None:
    strikes = option_strikes(atm=24000, step=50, depth=5)
    assert strikes[0] == 23750
    assert strikes[-1] == 24250
    assert len(strikes) == 11


def test_option_strikes_depth_zero() -> None:
    strikes = option_strikes(atm=24000, step=50, depth=0)
    assert strikes == [24000]


def test_option_strikes_ascending_order() -> None:
    strikes = option_strikes(atm=24000, step=100, depth=3)
    assert strikes == sorted(strikes)


def test_option_strikes_zero_step_raises() -> None:
    with pytest.raises(ValueError, match="step"):
        option_strikes(atm=24000, step=0)


def test_option_strikes_negative_step_raises() -> None:
    with pytest.raises(ValueError, match="step"):
        option_strikes(atm=24000, step=-50)


def test_option_strikes_negative_depth_raises() -> None:
    with pytest.raises(ValueError, match="depth"):
        option_strikes(atm=24000, step=50, depth=-1)


# ---------------------------------------------------------------------------
# expand_generic_symbols – validation and output ordering
# ---------------------------------------------------------------------------

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


def test_expand_generic_symbols_depth_zero() -> None:
    symbols = list(expand_generic_symbols("BANKNIFTY", 50000, step=100, depth=0))
    assert symbols == ["BANKNIFTY_50000_CE", "BANKNIFTY_50000_PE"]


def test_expand_generic_symbols_ce_before_pe() -> None:
    # Each strike pair must have CE immediately before PE.
    symbols = list(expand_generic_symbols("NIFTY", 24000, step=50, depth=2))
    for i in range(0, len(symbols), 2):
        assert symbols[i].endswith("_CE")
        assert symbols[i + 1].endswith("_PE")
        # Both share the same strike value
        assert symbols[i].split("_CE")[0] == symbols[i + 1].split("_PE")[0]


def test_expand_generic_symbols_total_count() -> None:
    depth = 3
    symbols = list(expand_generic_symbols("NIFTY", 24000, step=50, depth=depth))
    # (2 * depth + 1) strikes × 2 sides (CE + PE)
    assert len(symbols) == (2 * depth + 1) * 2


def test_expand_generic_symbols_zero_step_raises() -> None:
    with pytest.raises(ValueError, match="step"):
        list(expand_generic_symbols("NIFTY", 24000, step=0))


def test_expand_generic_symbols_negative_step_raises() -> None:
    with pytest.raises(ValueError, match="step"):
        list(expand_generic_symbols("NIFTY", 24000, step=-50))


def test_expand_generic_symbols_negative_depth_raises() -> None:
    with pytest.raises(ValueError, match="depth"):
        list(expand_generic_symbols("NIFTY", 24000, step=50, depth=-1))
