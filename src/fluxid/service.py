from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fluxid.market import INSTRUMENTS, expand_generic_symbols, nearest_strike
from fluxid.neo_client import MarketQuote, NeoApiClient


@dataclass
class OptionStrikeRow:
    """CE and PE quotes for a single strike, with ATM/moneyness metadata."""

    strike: int
    is_atm: bool
    moneyness: str  # "ATM", "ITM", or "OTM" (from the CE perspective)
    ce: MarketQuote | None
    pe: MarketQuote | None


@dataclass
class InstrumentSnapshot:
    code: str
    display_name: str
    future: MarketQuote
    spot: MarketQuote
    atm_strike: int
    option_quotes: list[MarketQuote]
    strike_rows: list[OptionStrikeRow] = field(default_factory=list)


def _parse_option_symbol(symbol: str) -> tuple[int, str] | None:
    """Extract ``(strike, side)`` from a symbol like ``'NIFTY_24000_CE'``.

    Returns ``None`` when the symbol cannot be parsed as an option symbol.
    """
    parts = symbol.rsplit("_", 2)
    if len(parts) == 3 and parts[2] in ("CE", "PE"):
        try:
            return int(parts[1]), parts[2]
        except ValueError:
            return None
    return None


def _strike_moneyness(strike: int, atm: int) -> str:
    """Return ``"ATM"``, ``"ITM"``, or ``"OTM"`` for *strike* vs *atm*.

    Moneyness is expressed from the Call (CE) perspective:
    strikes below ATM are ITM for calls, strikes above ATM are OTM for calls.
    """
    if strike == atm:
        return "ATM"
    return "ITM" if strike < atm else "OTM"


def build_strike_rows(
    option_quotes: list[MarketQuote],
    atm_strike: int,
) -> list[OptionStrikeRow]:
    """Group *option_quotes* into per-strike rows sorted ascending by strike.

    Each row pairs the CE and PE quotes for a strike (either may be ``None``
    when no matching quote was returned).  The rows are ordered from the
    lowest strike to the highest so the template can render them naturally.
    """
    ce_map: dict[int, MarketQuote] = {}
    pe_map: dict[int, MarketQuote] = {}
    for quote in option_quotes:
        parsed = _parse_option_symbol(quote.symbol)
        if parsed is None:
            continue
        strike, side = parsed
        if side == "CE":
            ce_map[strike] = quote
        else:
            pe_map[strike] = quote

    all_strikes = sorted(ce_map.keys() | pe_map.keys())
    rows: list[OptionStrikeRow] = []
    for strike in all_strikes:
        rows.append(
            OptionStrikeRow(
                strike=strike,
                is_atm=(strike == atm_strike),
                moneyness=_strike_moneyness(strike, atm_strike),
                ce=ce_map.get(strike),
                pe=pe_map.get(strike),
            )
        )
    return rows


class DashboardService:
    def __init__(self, neo: NeoApiClient, option_depth: int = 5) -> None:
        self.neo = neo
        self.option_depth = option_depth

    async def load_dashboard_data(self) -> list[InstrumentSnapshot]:
        snapshots: list[InstrumentSnapshot] = []
        for instrument in INSTRUMENTS:
            spot_symbol = f"{instrument.code}_SPOT"
            futures_symbol = f"{instrument.code}_FUT"

            spot, future = await asyncio.gather(
                self.neo.get_quote(spot_symbol),
                self.neo.get_quote(futures_symbol),
            )
            atm = nearest_strike(spot.ltp, instrument.option_step)

            option_symbols = list(
                expand_generic_symbols(
                    index_code=instrument.code,
                    spot_price=spot.ltp,
                    step=instrument.option_step,
                    depth=self.option_depth,
                )
            )
            option_quotes = await asyncio.gather(*(self.neo.get_quote(symbol) for symbol in option_symbols))
            option_quotes_list = sorted(option_quotes, key=lambda q: q.symbol)

            snapshots.append(
                InstrumentSnapshot(
                    code=instrument.code,
                    display_name=instrument.display_name,
                    future=future,
                    spot=spot,
                    atm_strike=atm,
                    option_quotes=option_quotes_list,
                    strike_rows=build_strike_rows(option_quotes_list, atm),
                )
            )
        return snapshots
