# US Market Live Feed (Side-by-Side with India) — Low-Level Design

## 1) Objective

Add a **US market live feed** next to the current India market feed so users can compare both markets in one view.

The feature should:
- keep current India feed behavior unchanged,
- add US tickers with live quote refresh,
- render India and US panels **side by side** on desktop (stacked on narrow screens),
- isolate failures so one market region can still render when the other fails.

---

## 2) Scope

### In scope
- Backend domain model for multi-region feed cards.
- Per-region quote loading pipeline (India + US).
- Region-aware ticker configuration.
- Dashboard template update for side-by-side rendering.
- Partial-failure error handling and freshness indicators.

### Out of scope (phase-2+)
- New provider onboarding for non-US ex-US markets.
- Tick-level websocket streaming (this design stays polling-based like current app).
- Portfolio/watchlist personalization.

---

## 3) Functional requirements

1. Dashboard shows two columns:
   - **India Markets**
   - **US Markets**
2. Each column shows configured tickers with:
   - symbol, display name,
   - LTP,
   - absolute change,
   - percent change,
   - optional volume.
3. Auto refresh interval uses existing `FLUXID_REFRESH_SECONDS`.
4. If one region fails:
   - failed region shows inline error,
   - other region still displays latest successful data.
5. Market-closed state is region-specific (India holiday/weekend rules should not suppress US section, and vice versa).

---

## 4) Proposed low-level architecture

## 4.1 Data model additions (`src/fluxid/service.py`)

Add regionized snapshot models (new dataclasses):

```py
@dataclass
class TickerSnapshot:
    symbol: str
    display_name: str
    ltp: float
    change: float | None
    pct_change: float | None
    volume: float | None
    currency: str
    last_trade_time: str | None

@dataclass
class RegionFeedSnapshot:
    region_code: str          # "IN" | "US"
    region_name: str          # "India Markets" | "US Markets"
    market_open: bool
    generated_at: datetime
    tickers: list[TickerSnapshot]
    error_message: str = ""
```

Introduce a new service method:

```py
async def load_multi_region_dashboard_data(self) -> list[RegionFeedSnapshot]:
    ...
```

This method orchestrates independent fetches for each region using `asyncio.gather(..., return_exceptions=True)`.

## 4.2 Configuration additions (`src/fluxid/config.py` + `src/fluxid/market.py`)

Add configurable ticker groups:

- `FLUXID_INDIA_TICKERS` (default: existing NIFTY/BANKNIFTY set)
- `FLUXID_US_TICKERS` (default: `SPY,QQQ,DIA,IWM,AAPL,MSFT,NVDA,TSLA`)

Define region metadata in `market.py`:

- exchange timezone,
- open/close times,
- market-day evaluator.

Suggested helpers:

```py
def is_market_open_india(now: datetime | None = None) -> bool: ...
def is_market_open_us(now: datetime | None = None) -> bool: ...
def is_market_day_india(now: datetime | None = None) -> bool: ...
def is_market_day_us(now: datetime | None = None) -> bool: ...
```

> Initial version can use weekday + session hours; holiday calendar support can be added in a follow-up task.

## 4.3 Quote provider abstraction (`src/fluxid/neo_client.py` + optional provider interface)

Current provider is Neo-focused for India instruments. US symbols may require a different upstream contract.

Design a provider protocol:

```py
class QuoteProvider(Protocol):
    async def get_quote(self, symbol: str, region: str) -> MarketQuote: ...
```

Implementation plan:
- keep Neo adapter as `NeoQuoteProvider` for India,
- add `UsQuoteProvider` (API adapter to selected US source),
- create `CompositeQuoteProvider` routing by region.

This avoids invasive changes in dashboard service and keeps region differences behind provider boundary.

## 4.4 Request flow update (`src/fluxid/main.py`)

Current `/` route returns one `snapshots` list for India options.

For side-by-side regional feed:
- add `regional_snapshots` to template context,
- keep existing option-chain workflows untouched,
- run regional loader regardless of India derivatives option-chain requirements.

Pseudo flow:

1. `regional_snapshots = await service.load_multi_region_dashboard_data()`
2. return template with both legacy fields and new regional field during migration.

## 4.5 Template/UI update (`src/fluxid/templates/dashboard.html`)

Add responsive 2-column layout:

- Desktop (`min-width: 1024px`): 2 equal columns.
- Mobile/tablet: stack sections.

Each region card shows:
- region title + market status badge (`OPEN`/`CLOSED`),
- last updated timestamp,
- compact table/list of ticker rows.

Example layout blocks:

- `.regions-grid`
- `.region-panel`
- `.ticker-table`

Keep existing option-chain section below, or move to dedicated tab in later phase.

## 4.6 Error handling and fallback

- Each region fetch wrapped independently.
- On exception:
  - set `error_message` on the corresponding `RegionFeedSnapshot`,
  - set `tickers=[]`,
  - do not raise from aggregate loader.
- Top-level route should only fail for catastrophic template/runtime errors.

## 4.7 Performance/concurrency

- Fetch ticker quotes concurrently per region.
- Fetch both regions concurrently.
- Optional guardrail: semaphore for upstream rate limits.

Complexity target:
- O(n) quote calls where n = total configured tickers,
- one render pass with pre-aggregated region payload.

---

## 5) Data contract to template

Proposed context key:

```py
context["regional_snapshots"] = [
  RegionFeedSnapshot(...),
  RegionFeedSnapshot(...),
]
```

Template assumptions:
- always iterate fixed order `IN`, then `US`.
- each region can independently contain error text and empty ticker list.

---

## 6) Implementation task breakdown

## Phase 1 — Domain + config foundation
1. Add region/ticker config settings and defaults.
2. Add region market-time helpers.
3. Add `TickerSnapshot` and `RegionFeedSnapshot` dataclasses.

## Phase 2 — Service orchestration
4. Add provider-routing abstraction for region-specific quote sources.
5. Implement `load_multi_region_dashboard_data()`.
6. Add partial-failure handling and log region-level errors.

## Phase 3 — UI rendering
7. Update dashboard context plumbing in `main.py`.
8. Add side-by-side region grid and ticker table in template.
9. Add status/freshness badges and empty/error states.

## Phase 4 — Validation
10. Unit tests for region market-hour helper logic.
11. Unit tests for service aggregator success + partial failure paths.
12. Template smoke test for presence of both region sections.

## Phase 5 — Operational hardening (recommended)
13. Add structured logs: region, symbol, latency, error code.
14. Add basic in-memory cache with short TTL (2–5s) to smooth provider spikes.
15. Add feature flag `FLUXID_ENABLE_US_FEED` for controlled rollout.

---

## 7) Acceptance criteria

- Dashboard renders both India and US market sections side by side on desktop.
- Auto-refresh updates both sections with latest available values.
- One-region outage does not blank the other region.
- Existing option-chain page remains unaffected.
- Test suite includes new region loader and market-session coverage.

---

## 8) Risks and mitigations

1. **US provider schema mismatch**
   - Mitigation: normalize via provider interface + strict parser tests.
2. **Rate limits during concurrent polling**
   - Mitigation: bounded concurrency, short cache TTL, retry with jitter.
3. **Timezone/session edge cases (DST)**
   - Mitigation: use timezone-aware datetimes and explicit US exchange timezone handling.

---

## 9) Suggested execution order (short)

1. Config + models
2. Provider abstraction + US adapter
3. Multi-region service loader
4. Dashboard UI side-by-side
5. Tests + rollout flag
