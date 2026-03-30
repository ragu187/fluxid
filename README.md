# Fluxid

Fluxid is a Python web app that shows live market snapshots for:

- NIFTY futures + ATM ±5 ITM/OTM option strikes (CE/PE)
- BANKNIFTY futures + ATM ±5 ITM/OTM option strikes (CE/PE)

The symbol generation logic is generic, so you can extend to more indices/instruments later.

## Pages

### Dashboard (`/`)

The dashboard presents each index instrument with:

- **Regional live feed strip** – India and US ticker panels shown side-by-side on desktop (stacked on mobile), each with symbol, LTP, change, % change, and volume.
- **Summary bar** – Spot LTP, Futures LTP, ATM strike, and Futures–Spot basis; change and % change shown in green/red.
- **Option chain table** – CE and PE quotes displayed side-by-side per strike row (CALL columns on the left, PUT columns on the right).  The ATM row is highlighted in amber; strikes below ATM are labelled **ITM** (in-the-money for calls), strikes above ATM are labelled **OTM**.
- **Formatted numerics** – LTP to 2 d.p.; change values with explicit sign (`+`/`−`); volume shown compactly (e.g. `1.2M`, `500K`).
- **Auto-refresh** – configurable via `FLUXID_REFRESH_SECONDS` (default 15 s).

### Option Chain OHLC (`/option-chain`)

A dedicated page showing Open / High / Low for both CE and PE sides of every option strike, updated from the same live feed as the dashboard.  The table layout is:

| CE Ticker | Open | High | Low | Strike | PE Ticker | Open | High | Low |
|-----------|------|------|-----|--------|-----------|------|------|-----|

- Values default to `–` when the upstream payload does not include OHLC fields.
- Auto-refreshes on the same `FLUXID_REFRESH_SECONDS` interval.
- A navigation link back to the main dashboard is included at the top of the page.

## 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Create your runtime env file:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
# India (Kotak Neo API)
FLUXID_NEO_API_KEY=your_kotak_neo_api_key
FLUXID_NEO_TOFT_KEY=optional_toft_key
FLUXID_NEO_API_BASE_URL=https://api.kotaksecurities.com/neo

# US (Alpaca Market Data API)
FLUXID_ALPACA_API_KEY_ID=your_alpaca_key_id
FLUXID_ALPACA_API_SECRET_KEY=your_alpaca_secret_key
# iex = free 15-min delayed feed; sip = real-time (paid Alpaca plan required)
FLUXID_ALPACA_FEED=iex

FLUXID_REFRESH_SECONDS=15
FLUXID_INDIA_TICKERS=NIFTY_SPOT,BANKNIFTY_SPOT
FLUXID_US_TICKERS=SPY,QQQ,DIA,IWM,AAPL,MSFT,NVDA,TSLA
```

## 2) Run locally

```bash
PYTHONPATH=src uvicorn fluxid.main:app --host 0.0.0.0 --port 8000 --reload
```

Open: http://localhost:8000

## 3) Test locally

### Unit tests

```bash
PYTHONPATH=src python -m pytest -q
```

### Syntax / import sanity

```bash
PYTHONPATH=src python -m compileall src tests
```

### API contract smoke-test (recommended before market hours)

**Neo (India feed)** – verify your Kotak Neo credentials:

```bash
python - <<'PY'
import asyncio
from fluxid.config import settings
from fluxid.neo_client import NeoApiClient

async def main():
    client = NeoApiClient(
        base_url=settings.neo_api_base_url,
        api_key=settings.neo_api_key,
        toft_key=settings.neo_toft_key,
    )
    quote = await client.get_quote("NIFTY_SPOT")
    print("Connected. LTP:", quote.ltp)

asyncio.run(main())
PY
```

If this fails, update `src/fluxid/neo_client.py` endpoint/query-key mapping to match your account's exact Neo API contract.

**Alpaca (US feed)** – verify your Alpaca credentials:

```bash
python - <<'PY'
import asyncio
from fluxid.config import settings
from fluxid.alpaca_client import AlpacaApiClient

async def main():
    client = AlpacaApiClient(
        base_url=settings.alpaca_data_base_url,
        key_id=settings.alpaca_api_key_id,
        secret_key=settings.alpaca_api_secret_key,
        feed=settings.alpaca_feed,
    )
    quote = await client.get_quote("SPY")
    print("Connected. SPY LTP:", quote.ltp)

asyncio.run(main())
PY
```

## Docker Compose (standardized local run)

1. Copy environment file and add your credentials:

```bash
cp .env.example .env
```

2. Build and start the app:

```bash
docker compose up --build
```

3. Open `http://localhost:8000`.

4. Stop the app:

```bash
docker compose down
```

## Docker installation

If you need Docker for local tooling, use the cross-platform installation steps (including full Windows + WSL2 setup) in `docs/local-deployment.md` under **"Docker installation (macOS/Linux + Windows)"`.

## Notes for Kotak Neo API integration

API contracts can vary by account/app version. Fluxid includes a resilient adapter (`NeoApiClient`) with fallback endpoint and query-key attempts. If your account uses different paths, update `NeoApiClient._fetch_quote_payload()` in `src/fluxid/neo_client.py`.

The dashboard intentionally loads India instrument data only on market weekdays (evaluated in the Asia/Kolkata exchange timezone).

## Notes for Alpaca API integration (US feed)

US equities data (SPY, QQQ, AAPL, etc.) is fetched via the [Alpaca Market Data API v2](https://docs.alpaca.markets/reference/stocksnapshots).

- **Free tier** (`FLUXID_ALPACA_FEED=iex`): Uses the IEX feed — quotes are approximately 15 minutes delayed but require no paid subscription.
- **Real-time** (`FLUXID_ALPACA_FEED=sip`): Uses the consolidated SIP feed — requires a paid Alpaca subscription.

The `AlpacaApiClient` calls the `/v2/stocks/snapshots` endpoint once per symbol.  Each snapshot response contains:

| Alpaca field | Maps to `MarketQuote` |
|---|---|
| `latestTrade.p` | `ltp` |
| `dailyBar.o/h/l/v` | `open` / `high` / `low` / `volume` |
| `latestTrade.p − prevDailyBar.c` | `change` / `pct_change` |

Sign up for a free Alpaca account at <https://alpaca.markets>.

## Design notes

- Multi-region (India + US) side-by-side live feed LLD and implementation task breakdown: `docs/us-market-live-feed-lld.md`.
