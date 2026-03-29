from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from fluxid.config import settings
from fluxid.market import is_market_day
from fluxid.neo_client import NeoApiClient, NeoApiError
from fluxid.service import DashboardService

app = FastAPI(title=settings.app_name)
templates = Jinja2Templates(directory="src/fluxid/templates")


def _format_volume_compact(value: float | None) -> str:
    """Format trading volume compactly: 1 234 567 → '1.2M', 5 000 → '5K'."""
    if value is None:
        return "-"
    v = int(value)
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}K"
    return str(v)


templates.env.filters["fmt_volume"] = _format_volume_compact

neo = NeoApiClient(
    base_url=settings.neo_api_base_url,
    api_key=settings.neo_api_key,
    toft_key=settings.neo_toft_key,
)
service = DashboardService(neo=neo)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    market_open_day = is_market_day()
    snapshots = []
    regional_snapshots = await service.load_multi_region_dashboard_data()
    error_message = ""

    if market_open_day:
        try:
            snapshots = await service.load_dashboard_data()
        except NeoApiError as exc:
            error_message = str(exc)
    else:
        error_message = "Market is closed today. Live feed is active only on market days."

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "snapshots": snapshots,
            "regional_snapshots": regional_snapshots,
            "market_open_day": market_open_day,
            "error_message": error_message,
            "generated_at": datetime.now(),
            "refresh_seconds": settings.refresh_seconds,
            "app_name": settings.app_name,
        },
    )


@app.get("/option-chain", response_class=HTMLResponse)
async def option_chain(request: Request) -> HTMLResponse:
    market_open_day = is_market_day()
    instruments: list[tuple[str, str, list]] = []
    error_message = ""

    if market_open_day:
        try:
            instruments = await service.load_option_chain_ohlc_data()
        except NeoApiError as exc:
            error_message = str(exc)
    else:
        error_message = "Market is closed today. Live feed is active only on market days."

    return templates.TemplateResponse(
        request=request,
        name="option_chain.html",
        context={
            "instruments": instruments,
            "market_open_day": market_open_day,
            "error_message": error_message,
            "generated_at": datetime.now(),
            "refresh_seconds": settings.refresh_seconds,
            "app_name": settings.app_name,
        },
    )
