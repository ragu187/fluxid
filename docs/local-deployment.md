# Local Deployment Guide (Review & Enhancement)

This guide explains how to run **Fluxid** locally so reviewers and developers can validate behavior and iterate quickly.

## 1) Prerequisites

- Python **3.10+**
- `pip` and `venv`
- Valid Kotak/Kodak Neo API credentials (for live market data)

Optional but recommended:
- `curl` for API checks
- `pytest` (installed through dev dependencies)

## 2) Clone and enter the repository

```bash
git clone <your-repo-url>
cd fluxid
```

## 3) Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 4) Configure environment variables

Create a local runtime env file:

```bash
cp .env.example .env
```

Update `.env` with your credentials and desired refresh interval:

```env
FLUXID_NEO_API_KEY=your_kodak_neo_api_key
FLUXID_NEO_ACCESS_TOKEN=optional_access_token
FLUXID_NEO_API_BASE_URL=https://api.kotaksecurities.com/neo
FLUXID_REFRESH_SECONDS=15
```

## 5) Run the app locally

```bash
PYTHONPATH=src uvicorn fluxid.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the app in your browser:

- http://localhost:8000

## 6) Health and smoke checks

### Basic HTTP check

```bash
curl -I http://localhost:8000
```

Expected: `HTTP/1.1 200 OK` (or an app response indicating the server is running).

### Neo API contract check (recommended before market-hours validation)

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

If the smoke test fails, adjust endpoint/query-key mapping in `src/fluxid/neo_client.py` to match your specific Neo contract.

## 7) Validation for review

Run these checks before sharing changes:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m compileall src tests
```

## 8) Workflow for further enhancement

1. Create a feature branch from your latest main branch.
2. Make incremental changes with focused commits.
3. Re-run tests and compile checks.
4. Manually verify `http://localhost:8000` for UI/data behavior.
5. Open a pull request with:
   - Scope of change
   - Screenshots (if UI changed)
   - Risk/rollback notes

## 9) Troubleshooting

- **App fails to start**: confirm virtualenv is activated and dependencies are installed.
- **No live quotes**: verify `.env` credentials and Neo API base URL.
- **Import errors**: ensure `PYTHONPATH=src` is included when running app/tests.
- **Market data appears stale**: tune `FLUXID_REFRESH_SECONDS` and verify market-day behavior.

---

For an at-a-glance setup, see `README.md`. Use this document when onboarding reviewers or preparing enhancement cycles.
