from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from zoneinfo import ZoneInfo


# Exchange timezone for NSE/BSE (Indian Standard Time, UTC+5:30).
EXCHANGE_TZ: ZoneInfo = ZoneInfo("Asia/Kolkata")
US_EXCHANGE_TZ: ZoneInfo = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class IndexInstrument:
    code: str
    display_name: str
    option_step: int
    lot_size: int


INSTRUMENTS: list[IndexInstrument] = [
    IndexInstrument(code="NIFTY", display_name="NIFTY 50", option_step=50, lot_size=75),
    IndexInstrument(code="BANKNIFTY", display_name="NIFTY BANK", option_step=100, lot_size=15),
]


def _now_in_exchange_tz() -> datetime:
    """Return the current time expressed in the exchange timezone."""
    return datetime.now(tz=timezone.utc).astimezone(EXCHANGE_TZ)


def _now_in_us_exchange_tz() -> datetime:
    """Return the current time expressed in the US exchange timezone."""
    return datetime.now(tz=timezone.utc).astimezone(US_EXCHANGE_TZ)


def is_market_day(now: datetime | None = None) -> bool:
    """Return True when *now* falls on a weekday in the exchange timezone.

    If *now* is ``None`` the current wall-clock time is used, converted to
    the exchange timezone (Asia/Kolkata) before the weekday check.  If *now*
    is a timezone-aware :class:`~datetime.datetime` it is converted to the
    exchange timezone.  If *now* is a naive :class:`~datetime.datetime` it is
    assumed to already be in the exchange timezone and is used as-is.
    """
    if now is None:
        now = _now_in_exchange_tz()
    elif now.tzinfo is not None:
        # Aware datetime: convert to exchange timezone for a consistent check.
        now = now.astimezone(EXCHANGE_TZ)
    # Naive datetime is treated as already being in the exchange timezone.
    return now.weekday() < 5


def is_us_market_day(now: datetime | None = None) -> bool:
    """Return True when *now* falls on a weekday in US exchange timezone."""
    if now is None:
        now = _now_in_us_exchange_tz()
    elif now.tzinfo is not None:
        now = now.astimezone(US_EXCHANGE_TZ)
    return now.weekday() < 5


def is_market_day_india(now: datetime | None = None) -> bool:
    """Return True when *now* falls on a weekday in the India exchange timezone.

    Alias for :func:`is_market_day` provided for symmetry with the US helpers.
    """
    return is_market_day(now)


def is_market_day_us(now: datetime | None = None) -> bool:
    """Return True when *now* falls on a weekday in the US exchange timezone.

    Alias for :func:`is_us_market_day` provided for API symmetry.
    """
    return is_us_market_day(now)


def is_market_open_india(now: datetime | None = None) -> bool:
    """Return True when *now* is within NSE/BSE trading hours.

    Trading session: 09:15–15:30 IST on weekdays.
    If *now* is ``None`` the current wall-clock time is used.
    Timezone-aware values are converted to IST; naive values are treated as IST.
    """
    if now is None:
        now = _now_in_exchange_tz()
    elif now.tzinfo is not None:
        now = now.astimezone(EXCHANGE_TZ)
    if now.weekday() >= 5:
        return False
    session_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    session_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return session_start <= now <= session_end


def is_market_open_us(now: datetime | None = None) -> bool:
    """Return True when *now* is within NYSE/NASDAQ regular trading hours.

    Trading session: 09:30–16:00 ET on weekdays.
    If *now* is ``None`` the current wall-clock time is used.
    Timezone-aware values are converted to ET; naive values are treated as ET.
    """
    if now is None:
        now = _now_in_us_exchange_tz()
    elif now.tzinfo is not None:
        now = now.astimezone(US_EXCHANGE_TZ)
    if now.weekday() >= 5:
        return False
    session_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    session_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return session_start <= now <= session_end


def nearest_strike(price: float, step: int) -> int:
    """Return the strike price nearest to *price* on the *step* grid.

    Args:
        price: Underlying or futures price.
        step:  Strike interval (must be a positive integer).

    Raises:
        ValueError: If *step* is not a positive integer.
    """
    if step <= 0:
        raise ValueError(f"step must be a positive integer, got {step!r}")
    return int(round(price / step) * step)


def option_strikes(atm: int, step: int, depth: int = 5) -> list[int]:
    """Return the list of option strikes around *atm*.

    Generates ``2 * depth + 1`` strikes evenly spaced by *step*, centred on
    *atm* (i.e. from ``atm - depth * step`` to ``atm + depth * step``).

    Args:
        atm:   At-the-money strike.
        step:  Strike interval (must be a positive integer).
        depth: Number of strikes on each side of ATM (must be non-negative).

    Raises:
        ValueError: If *step* ≤ 0 or *depth* < 0.
    """
    if step <= 0:
        raise ValueError(f"step must be a positive integer, got {step!r}")
    if depth < 0:
        raise ValueError(f"depth must be non-negative, got {depth!r}")
    strikes: list[int] = []
    for offset in range(-depth, depth + 1):
        strikes.append(atm + offset * step)
    return strikes


def expand_generic_symbols(index_code: str, spot_price: float, step: int, depth: int = 5) -> Iterable[str]:
    """Yield CE and PE option symbols for strikes around the ATM of *spot_price*.

    Args:
        index_code:  Instrument code, e.g. ``"NIFTY"``.
        spot_price:  Current spot price used to derive ATM.
        step:        Strike interval (must be a positive integer).
        depth:       Number of strikes on each side of ATM (must be non-negative).

    Raises:
        ValueError: If *step* ≤ 0 or *depth* < 0.
    """
    if step <= 0:
        raise ValueError(f"step must be a positive integer, got {step!r}")
    if depth < 0:
        raise ValueError(f"depth must be non-negative, got {depth!r}")
    atm = nearest_strike(spot_price, step)
    for strike in option_strikes(atm=atm, step=step, depth=depth):
        yield f"{index_code}_{strike}_CE"
        yield f"{index_code}_{strike}_PE"
