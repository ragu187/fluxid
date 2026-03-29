from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fluxid.config import settings
from fluxid.market import INSTRUMENTS, expand_generic_symbols, is_market_day, is_us_market_day, nearest_strike
from fluxid.neo_client import CompositeQuoteProvider, MarketQuote, NeoApiClient


@dataclass
class OptionStrikeRow:
    """CE and PE quotes for a single strike, with ATM/moneyness metadata."""

    strike: int
    is_atm: bool
    moneyness: str  # "ATM", "ITM", or "OTM" (from the CE perspective)
    ce: MarketQuote | None
    pe: MarketQuote | None


@dataclass
class OptionChainOHLCRow:
    """OHLC data for CE and PE sides of a single option strike."""

    strike: int
    ce_symbol: str | None
    ce_open: float | None
    ce_high: float | None
    ce_low: float | None
    pe_symbol: str | None
    pe_open: float | None
    pe_high: float | None
    pe_low: float | None


@dataclass
class InstrumentSnapshot:
    code: str
    display_name: str
    future: MarketQuote
    spot: MarketQuote
    atm_strike: int
    option_quotes: list[MarketQuote]
    strike_rows: list[OptionStrikeRow] = field(default_factory=list)


@dataclass
class TickerSnapshot:
    symbol: str
    display_name: str
    ltp: float
    change: float | None
    pct_change: float | None
    volume: float | None
    currency: str
    last_trade_time: str | None = None


@dataclass
class RegionFeedSnapshot:
    region_code: str
    region_name: str
    market_open_day: bool
    generated_at: datetime
    tickers: list[TickerSnapshot] = field(default_factory=list)
    error_message: str = ""


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


def build_option_chain_ohlc_rows(
    option_quotes: list[MarketQuote],
) -> list[OptionChainOHLCRow]:
    """Build OHLC rows pairing CE and PE quotes by strike.

    Returns rows sorted ascending by strike.  Either side may be ``None``
    when only one leg was returned by the feed.
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
    rows: list[OptionChainOHLCRow] = []
    for strike in all_strikes:
        ce = ce_map.get(strike)
        pe = pe_map.get(strike)
        rows.append(
            OptionChainOHLCRow(
                strike=strike,
                ce_symbol=ce.symbol if ce else None,
                ce_open=ce.open if ce else None,
                ce_high=ce.high if ce else None,
                ce_low=ce.low if ce else None,
                pe_symbol=pe.symbol if pe else None,
                pe_open=pe.open if pe else None,
                pe_high=pe.high if pe else None,
                pe_low=pe.low if pe else None,
            )
        )
    return rows


class DashboardService:
    def __init__(self, neo: NeoApiClient, composite: CompositeQuoteProvider | None = None, option_depth: int = 5) -> None:
        self.neo = neo
        self.composite = composite
        self.option_depth = option_depth
        self._display_names = {
            "NIFTY_SPOT": "NIFTY 50",
            "BANKNIFTY_SPOT": "NIFTY BANK",
            "SPY": "SPDR S&P 500 ETF",
            "QQQ": "Invesco QQQ",
            "DIA": "SPDR Dow Jones Industrial Average ETF",
            "IWM": "iShares Russell 2000 ETF",
            "AAPL": "Apple",
            "MSFT": "Microsoft",
            "NVDA": "NVIDIA",
            "TSLA": "Tesla",
        }

    async def load_multi_region_dashboard_data(self) -> list[RegionFeedSnapshot]:
        tasks = [
            self._load_region_snapshot("IN", "India Markets", settings.india_tickers, is_market_day, "INR"),
        ]
        if settings.enable_us_feed:
            tasks.append(
                self._load_region_snapshot("US", "US Markets", settings.us_tickers, is_us_market_day, "USD"),
            )
        return list(await asyncio.gather(*tasks))

    async def _load_region_snapshot(
        self,
        region_code: str,
        region_name: str,
        symbols: tuple[str, ...],
        market_day_fn,
        currency: str,
    ) -> RegionFeedSnapshot:
        market_open_day = market_day_fn()
        snapshot = RegionFeedSnapshot(
            region_code=region_code,
            region_name=region_name,
            market_open_day=market_open_day,
            generated_at=datetime.now(tz=timezone.utc),
        )
        if not market_open_day:
            snapshot.error_message = "Market is closed today."
            return snapshot
        try:
            if self.composite is not None:
                quotes = await asyncio.gather(
                    *(self.composite.get_quote(symbol, region_code) for symbol in symbols)
                )
            else:
                quotes = await asyncio.gather(*(self.neo.get_quote(symbol) for symbol in symbols))
        except Exception as exc:  # noqa: BLE001 - expose upstream message region-wise.
            snapshot.error_message = str(exc)
            return snapshot

        snapshot.tickers = [self._to_ticker_snapshot(quote, currency) for quote in quotes]
        return snapshot

    def _to_ticker_snapshot(self, quote: MarketQuote, currency: str) -> TickerSnapshot:
        return TickerSnapshot(
            symbol=quote.symbol,
            display_name=self._display_names.get(quote.symbol, quote.symbol),
            ltp=quote.ltp,
            change=quote.change,
            pct_change=quote.pct_change,
            volume=quote.volume,
            currency=currency,
        )

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

    async def load_option_chain_ohlc_data(self) -> list[tuple[str, str, list[OptionChainOHLCRow]]]:
        """Load option-chain OHLC data for all instruments.

        Returns a list of ``(code, display_name, ohlc_rows)`` tuples,
        one per instrument, where *ohlc_rows* pairs CE/PE quotes by strike
        and exposes Open / High / Low for each side.
        """
        result: list[tuple[str, str, list[OptionChainOHLCRow]]] = []
        for instrument in INSTRUMENTS:
            spot_symbol = f"{instrument.code}_SPOT"
            spot = await self.neo.get_quote(spot_symbol)
            option_symbols = list(
                expand_generic_symbols(
                    index_code=instrument.code,
                    spot_price=spot.ltp,
                    step=instrument.option_step,
                    depth=self.option_depth,
                )
            )
            option_quotes = await asyncio.gather(*(self.neo.get_quote(symbol) for symbol in option_symbols))
            ohlc_rows = build_option_chain_ohlc_rows(list(option_quotes))
            result.append((instrument.code, instrument.display_name, ohlc_rows))
        return result
