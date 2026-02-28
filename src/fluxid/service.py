from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fluxid.market import INSTRUMENTS, expand_generic_symbols, nearest_strike
from fluxid.neo_client import MarketQuote, NeoApiClient


@dataclass
class InstrumentSnapshot:
    code: str
    display_name: str
    future: MarketQuote
    spot: MarketQuote
    atm_strike: int
    option_quotes: list[MarketQuote]


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

            snapshots.append(
                InstrumentSnapshot(
                    code=instrument.code,
                    display_name=instrument.display_name,
                    future=future,
                    spot=spot,
                    atm_strike=atm,
                    option_quotes=sorted(option_quotes, key=lambda q: q.symbol),
                )
            )
        return snapshots
