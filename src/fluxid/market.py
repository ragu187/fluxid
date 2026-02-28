from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


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


def is_market_day(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return now.weekday() < 5


def nearest_strike(price: float, step: int) -> int:
    return int(round(price / step) * step)


def option_strikes(atm: int, step: int, depth: int = 5) -> list[int]:
    strikes: list[int] = []
    for offset in range(-depth, depth + 1):
        strikes.append(atm + offset * step)
    return strikes


def expand_generic_symbols(index_code: str, spot_price: float, step: int, depth: int = 5) -> Iterable[str]:
    atm = nearest_strike(spot_price, step)
    for strike in option_strikes(atm=atm, step=step, depth=depth):
        yield f"{index_code}_{strike}_CE"
        yield f"{index_code}_{strike}_PE"
