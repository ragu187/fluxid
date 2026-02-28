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

neo = NeoApiClient(
    base_url=settings.neo_api_base_url,
    api_key=settings.neo_api_key,
    access_token=settings.neo_access_token,
)
service = DashboardService(neo=neo)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    market_open_day = is_market_day()
    snapshots = []
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
            "market_open_day": market_open_day,
            "error_message": error_message,
            "generated_at": datetime.now(),
            "refresh_seconds": settings.refresh_seconds,
            "app_name": settings.app_name,
        },
    )
