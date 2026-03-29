"""Template smoke tests – verify that both region sections render correctly."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from fluxid.service import RegionFeedSnapshot, TickerSnapshot


TEMPLATE_DIR = Path(__file__).parent.parent / "src" / "fluxid" / "templates"


@pytest.fixture()
def jinja_env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)

    def _fmt_volume(value: float | None) -> str:
        if value is None:
            return "-"
        v = int(value)
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v / 1_000:.0f}K"
        return str(v)

    env.filters["fmt_volume"] = _fmt_volume
    return env


def _make_region(
    region_code: str,
    region_name: str,
    tickers: list[TickerSnapshot],
    error_message: str = "",
) -> RegionFeedSnapshot:
    return RegionFeedSnapshot(
        region_code=region_code,
        region_name=region_name,
        market_open_day=bool(tickers),
        generated_at=datetime.now(tz=timezone.utc),
        tickers=tickers,
        error_message=error_message,
    )


def test_dashboard_renders_both_region_sections(jinja_env: Environment) -> None:
    india = _make_region(
        "IN",
        "India Markets",
        [TickerSnapshot("NIFTY_SPOT", "NIFTY 50", 24100.0, 20.0, 0.08, 1000, currency="INR")],
    )
    us = _make_region(
        "US",
        "US Markets",
        [TickerSnapshot("AAPL", "Apple", 210.0, -1.2, -0.57, 2000, currency="USD")],
    )

    template = jinja_env.get_template("dashboard.html")
    html = template.render(
        app_name="TestApp",
        regional_snapshots=[india, us],
        snapshots=[],
        market_open_day=True,
        error_message="",
        generated_at=datetime.now(),
        refresh_seconds=15,
    )

    assert "India Markets" in html
    assert "US Markets" in html
    assert "NIFTY_SPOT" in html
    assert "AAPL" in html


def test_dashboard_renders_region_open_status(jinja_env: Environment) -> None:
    india = _make_region(
        "IN",
        "India Markets",
        [TickerSnapshot("NIFTY_SPOT", "NIFTY 50", 24100.0, None, None, None, currency="INR")],
    )
    closed_us = _make_region("US", "US Markets", [], error_message="Market is closed today.")

    template = jinja_env.get_template("dashboard.html")
    html = template.render(
        app_name="TestApp",
        regional_snapshots=[india, closed_us],
        snapshots=[],
        market_open_day=True,
        error_message="",
        generated_at=datetime.now(),
        refresh_seconds=15,
    )

    assert "OPEN" in html
    assert "CLOSED" in html
    assert "Market is closed today." in html


def test_dashboard_renders_region_error(jinja_env: Environment) -> None:
    india_error = _make_region("IN", "India Markets", [], error_message="upstream failure")
    us = _make_region(
        "US",
        "US Markets",
        [TickerSnapshot("SPY", "SPDR S&P 500 ETF", 500.0, 2.5, 0.5, 50_000_000, currency="USD")],
    )

    template = jinja_env.get_template("dashboard.html")
    html = template.render(
        app_name="TestApp",
        regional_snapshots=[india_error, us],
        snapshots=[],
        market_open_day=True,
        error_message="",
        generated_at=datetime.now(),
        refresh_seconds=15,
    )

    assert "upstream failure" in html
    assert "SPY" in html
