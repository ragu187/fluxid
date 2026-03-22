# Fluxid

Fluxid is a Python web app that shows live market snapshots for:

- NIFTY futures + ATM ±5 ITM/OTM option strikes (CE/PE)
- BANKNIFTY futures + ATM ±5 ITM/OTM option strikes (CE/PE)

The symbol generation logic is generic, so you can extend to more indices/instruments later.

## Dashboard

The dashboard presents each index instrument with:

- **Summary bar** – Spot LTP, Futures LTP, ATM strike, and Futures–Spot basis; change and % change shown in green/red.
- **Option chain table** – CE and PE quotes displayed side-by-side per strike row (CALL columns on the left, PUT columns on the right).  The ATM row is highlighted in amber; strikes below ATM are labelled **ITM** (in-the-money for calls), strikes above ATM are labelled **OTM**.
- **Formatted numerics** – LTP to 2 d.p.; change values with explicit sign (`+`/`−`); volume shown compactly (e.g. `1.2M`, `500K`).
- **Auto-refresh** – configurable via `FLUXID_REFRESH_SECONDS` (default 15 s).

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
FLUXID_NEO_API_KEY=your_kotak_neo_api_key
FLUXID_NEO_ACCESS_TOKEN=optional_access_token
# change if your contract uses a different host
FLUXID_NEO_API_BASE_URL=https://api.kotaksecurities.com/neo
FLUXID_REFRESH_SECONDS=15
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

Use your Neo credentials in `.env`, then quickly verify that your configured API host and auth work.

```bash
python - <<'PY'
import asyncio
from fluxid.config import settings
from fluxid.neo_client import NeoApiClient

async def main():
    client = NeoApiClient(
        base_url=settings.neo_api_base_url,
        api_key=settings.neo_api_key,
        access_token=settings.neo_access_token,
    )
    quote = await client.get_quote("NIFTY_SPOT")
    print("Connected. LTP:", quote.ltp)

asyncio.run(main())
PY
```

If this fails, update `src/fluxid/neo_client.py` endpoint/query-key mapping to match your account's exact Neo API contract.

## Docker installation

If you need Docker for local tooling, use the cross-platform installation steps (including full Windows + WSL2 setup) in `docs/local-deployment.md` under **"Docker installation (macOS/Linux + Windows)"`.

## Notes for Kotak Neo API integration

API contracts can vary by account/app version. Fluxid includes a resilient adapter (`NeoApiClient`) with fallback endpoint and query-key attempts. If your account uses different paths, update `NeoApiClient._fetch_quote_payload()` in `src/fluxid/neo_client.py`.

The dashboard intentionally loads data only on market weekdays (evaluated in the Asia/Kolkata exchange timezone).
