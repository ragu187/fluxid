# Local Deployment Guide (Review & Enhancement)

This guide explains how to run **Fluxid** locally so reviewers and developers can validate behavior and iterate quickly.

## 1) Prerequisites

- Python **3.10+**
- `pip` and `venv`
- Valid Kotak/Kodak Neo API credentials (for live market data)

Optional but recommended:
- `curl` for API checks
- `pytest` (installed through dev dependencies)

## 2) Docker installation (macOS/Linux + Windows)

If you prefer containerized workflows (or need Docker for local tooling), install Docker before running the app.

### 2.1 macOS and Linux quick setup

1. Install Docker Desktop (macOS) or Docker Engine + Docker Compose plugin (Linux).
2. Start Docker.
3. Verify installation:

```bash
docker --version
docker compose version
```

### 2.2 Windows setup (full step-by-step)

1. **Confirm platform requirements**
   - Windows 10/11 64-bit.
   - Hardware virtualization enabled in BIOS/UEFI.
   - WSL 2 support available.

2. **Enable required Windows features (PowerShell as Administrator)**

```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

3. **Reboot Windows** when prompted.

4. **Install/upgrade WSL and set default version to 2**

```powershell
wsl --install
wsl --set-default-version 2
```

5. **Install a Linux distribution** from Microsoft Store (Ubuntu is commonly used) and complete first-time user creation.

6. **Install Docker Desktop for Windows**
   - Download from Docker's official website.
   - Run installer.
   - Ensure **"Use WSL 2 instead of Hyper-V"** (or equivalent WSL 2 backend option) is enabled.

7. **Enable WSL integration in Docker Desktop**
   - Open Docker Desktop → **Settings** → **Resources** → **WSL Integration**.
   - Enable integration for your installed distro (for example, Ubuntu).

8. **Start Docker Desktop** and wait until status is "Docker Desktop is running".

9. **Verify from both PowerShell and WSL**

```powershell
docker --version
docker compose version
docker run --rm hello-world
```

In your WSL shell:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

10. **Optional (non-admin Docker usage in Linux distros)**

```bash
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker "$USER"
newgrp docker
```

11. **If Docker commands fail on Windows, check these quickly**
   - `wsl -l -v` shows your distro as version 2.
   - Docker Desktop WSL integration is turned on for your distro.
   - Virtualization is enabled in BIOS/UEFI.
   - Corporate VPN/security tools are not blocking Docker networking.

## 3) Clone and enter the repository

```bash
git clone <your-repo-url>
cd fluxid
```

## 4) Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

> Windows PowerShell activation command:
>
> ```powershell
> .\.venv\Scripts\Activate.ps1
> ```

## 5) Configure environment variables

Create a local runtime env file:

```bash
cp .env.example .env
```

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Update `.env` with your credentials and desired refresh interval:

```env
FLUXID_NEO_API_KEY=your_kodak_neo_api_key
FLUXID_NEO_ACCESS_TOKEN=optional_access_token
FLUXID_NEO_API_BASE_URL=https://api.kotaksecurities.com/neo
FLUXID_REFRESH_SECONDS=15
```

## 6) Run the app locally

macOS/Linux:

```bash
PYTHONPATH=src uvicorn fluxid.main:app --host 0.0.0.0 --port 8000 --reload
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
uvicorn fluxid.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the app in your browser:

- http://localhost:8000

## 7) Health and smoke checks

### Basic HTTP check

macOS/Linux:

```bash
curl -I http://localhost:8000
```

Windows PowerShell:

```powershell
curl.exe -I http://localhost:8000
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

## 8) Validation for review

Run these checks before sharing changes.

macOS/Linux:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m compileall src tests
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m pytest -q
python -m compileall src tests
```

## 9) Workflow for further enhancement

1. Create a feature branch from your latest main branch.
2. Make incremental changes with focused commits.
3. Re-run tests and compile checks.
4. Manually verify `http://localhost:8000` for UI/data behavior.
5. Open a pull request with:
   - Scope of change
   - Screenshots (if UI changed)
   - Risk/rollback notes

## 10) Troubleshooting

- **App fails to start**: confirm virtualenv is activated and dependencies are installed.
- **No live quotes**: verify `.env` credentials and Neo API base URL.
- **Import errors**: ensure `PYTHONPATH=src` is included when running app/tests.
- **Market data appears stale**: tune `FLUXID_REFRESH_SECONDS` and verify market-day behavior.
- **Docker not found on Windows**: confirm Docker Desktop is running and WSL integration is enabled.

---

For an at-a-glance setup, see `README.md`. Use this document when onboarding reviewers or preparing enhancement cycles.
