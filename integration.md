# Frontend Integration Plan

## Objective

Integrate the existing frontend with the backend that already exists in this repository so the dashboard stops depending on mock market data and instead uses:

- real NIFTY 50 benchmark data
- real symbol OHLC history
- real live signal data
- real per-symbol strategy diagnostics
- real model outputs where available

This document is based on the current codebase, not on a greenfield design.

---

## Current Backend State

### Existing Services

#### 1. Model Service
Path: `services/model-service`

Current endpoints:

- `GET /health`
- `POST /predict`

Current responsibility:

- Loads trained ensemble artifacts
- Scores a single feature payload
- Returns:
  - `probability`
  - `expected_return`
  - `expected_drawdown`
  - `confidence`
  - `regime` (currently defaulted)
  - `is_anomaly`
  - `models_used`

Relevant files:

- `services/model-service/app/main.py`
- `services/model-service/app/services/ensemble.py`
- `services/model-service/app/schemas/prediction.py`

#### 2. Signal Service
Path: `services/signal-service`

Current endpoints:

- `GET /health`
- `POST /reset_day`
- `POST /process`
- `GET /signals`

Current responsibility:

- Runs 6 strategies plus regime gating
- Calls model-service for scoring
- Logs raw `StrategySignal`
- Stores filtered `TradeSignal`
- Exposes live trade alerts to frontend via `/signals`

Relevant files:

- `services/signal-service/app/main.py`
- `services/signal-service/app/models/schema.py`
- `services/signal-service/app/schemas/signal.py`
- `services/signal-service/app/services/model_client.py`

### Existing Data Paths

#### 1. Parquet Feature Store
- Directory: `data/mode_ready_data`
- Contents: enriched parquet files per symbol

#### 2. PostgreSQL Ingestion Path
- `scripts/ingest_data.py` ingests `_enriched.parquet` files into table `ohlcv_enriched`
- Database connection comes from `.env` via `DATABASE_URL`

#### 3. Signal Tables Already Used by Backend

- `strategy_signals`
- `trade_signals`

These are already defined in:

- `services/signal-service/app/models/schema.py`

---

## Current Frontend State

Path: `frontend`

What already works:

- Dashboard layout
- NIFTY 50 benchmark card
- TradingView-style candlestick component
- day / month / year switching
- searchable symbol deck
- clickable signal cards
- per-symbol 7-method panel
- live `/signals` polling

What is still mock:

- symbol list and benchmark data
- chart OHLC history
- per-symbol strategy states
- per-symbol summary stats

Current mock source:

- `frontend/src/mockMarket.js`

---

## Integration Principle

Do not force the frontend to talk directly to training scripts, parquet files, or raw database structure.

Instead:

1. Keep frontend talking only to HTTP APIs.
2. Add frontend-facing read APIs in backend.
3. Reuse current backend services where possible.
4. Introduce a dedicated market-data read service only if signal-service becomes overloaded.

Short version:

- keep `model-service` focused on prediction
- keep `signal-service` focused on live signal generation and signal retrieval
- add read APIs for chart/history/insight data

---

## Recommended Architecture

### Phase 1 Recommendation

Add the missing read endpoints to `signal-service` first.

Reason:

- frontend already talks to `signal-service`
- it already has DB access
- it already owns strategy orchestration
- this is the fastest path to a working integrated dashboard

### Phase 2 Recommendation

Extract read-heavy market/history APIs into a separate `data-service` later if needed.

Reason:

- history endpoints can become large and high-volume
- chart/history workloads are different from signal generation workloads
- separating them later is safer than over-designing now

---

## Backend APIs Required For Frontend

The frontend currently needs 4 data categories:

1. Benchmark overview
2. Symbol universe / search
3. OHLC chart history
4. Symbol insights including 7 strategy outputs

### 1. Benchmark Endpoint

Suggested endpoint:

- `GET /benchmark`

Suggested query params:

- `symbol=NIFTY50`
- `range=1D|1M|1Y`

Purpose:

- power benchmark cards
- power default chart on first page load

Suggested response:

```json
{
  "status": "success",
  "data": {
    "symbol": "NIFTY50",
    "label": "NIFTY 50",
    "last_price": 22480.45,
    "change_pct": 0.84,
    "volume": 1840000000000,
    "breadth": {
      "advancers": 34,
      "decliners": 16
    },
    "series": [
      { "time": 1712553600, "open": 22320.1, "high": 22410.4, "low": 22280.2, "close": 22396.8 }
    ]
  },
  "error": null
}
```

### 2. Symbol Universe Endpoint

Suggested endpoint:

- `GET /symbols`

Suggested query params:

- `q=<search text>`
- `limit=50`

Purpose:

- power search box
- power watchlist / symbol deck

Suggested response:

```json
{
  "status": "success",
  "data": [
    {
      "symbol": "RELIANCE",
      "label": "Reliance Industries",
      "sector": "Energy",
      "last_price": 2968.2,
      "change_pct": 1.36
    }
  ],
  "error": null
}
```

### 3. Chart History Endpoint

Suggested endpoint:

- `GET /history`

Suggested query params:

- `symbol=RELIANCE`
- `range=1D|1M|1Y`
- optional `interval=1m|5m|1d|1wk`

Purpose:

- power TradingView-style chart for benchmark and selected symbol

Suggested response:

```json
{
  "status": "success",
  "data": {
    "symbol": "RELIANCE",
    "range": "1D",
    "interval": "1m",
    "series": [
      { "time": 1712553600, "open": 2952.1, "high": 2960.8, "low": 2948.0, "close": 2958.2 }
    ]
  },
  "error": null
}
```

### 4. Symbol Insight Endpoint

Suggested endpoint:

- `GET /insights`

Suggested query params:

- `symbol=RELIANCE`

Purpose:

- power right-side symbol detail
- power the 7-method panel
- power summary stats for selected symbol

Suggested response:

```json
{
  "status": "success",
  "data": {
    "symbol": "RELIANCE",
    "label": "Reliance Industries",
    "sector": "Energy",
    "last_price": 2968.2,
    "change_pct": 1.36,
    "intraday_change_pct": 0.44,
    "volume": 3240000000,
    "regime": "Trending",
    "latest_model_prediction": {
      "probability": 0.81,
      "expected_return": 1.42,
      "expected_drawdown": 0.38,
      "confidence": 0.79,
      "is_anomaly": false
    },
    "strategies": [
      {
        "name": "ORB",
        "status": "Bullish",
        "confidence": 0.81,
        "note": "Held above opening range high",
        "last_signal_time": "2026-04-06T10:17:00+05:30"
      }
    ]
  },
  "error": null
}
```

---

## Where Each Endpoint Should Get Data

### `/signals`

Source:

- existing `trade_signals` table

Service:

- keep in `signal-service`

No architectural change required.

### `/history`

Primary source:

- `ohlcv_enriched` table in PostgreSQL

Fallback source:

- parquet files in `data/mode_ready_data`

Reason:

- frontend needs filtered, small chart slices
- DB is better for query-based retrieval
- parquet can be fallback during transition

### `/symbols`

Primary source:

- distinct symbols from `ohlcv_enriched`

Optional enrichment:

- static symbol metadata map for human-readable company name / sector if DB does not contain reliable metadata

### `/benchmark`

Preferred source:

- dedicated benchmark table or benchmark parquet if available

If not available yet:

- compute benchmark from a chosen symbol universe or ingest NIFTY benchmark separately

Important:

- do not fake NIFTY 50 from one stock
- if actual NIFTY benchmark history is missing, that is a data gap and should be fixed explicitly

### `/insights`

This should be assembled from multiple sources:

1. latest symbol row from `ohlcv_enriched`
2. latest raw `strategy_signals` rows for that symbol
3. latest filtered `trade_signals` rows for that symbol
4. optional fresh prediction call into `model-service`

This is an aggregation endpoint.

---

## How To Build Symbol Insights Correctly

The frontend wants:

- "what are the 7 methods saying about RELIANCE?"

The current backend does not directly expose a stable 7-strategy read model.

That needs to be created.

### Required Strategy Read Model

For each symbol, the backend should produce exactly one normalized record per strategy:

- `name`
- `status`
- `confidence`
- `note`
- `direction`
- `last_evaluated_at`
- `triggered`
- `passed_filter`

### Important Constraint

Current `signal-service` only persists raw strategy rows when a strategy actually generates a signal in `/process`.

That means:

- if a strategy did not trigger, there may be no persisted row
- frontend cannot infer "inactive" vs "not evaluated"

### Recommendation

Add a normalized strategy evaluation layer.

Two valid approaches:

#### Option A. Persist Every Strategy Evaluation

On each `/process` call, write one row per evaluated strategy, even if it did not trigger.

Add fields like:

- `evaluated`
- `triggered`
- `passed_filter`
- `status_reason`

Best long-term option.

#### Option B. Build Read-Time Strategy State

For `/insights`, re-run the strategy logic on the latest available symbol row and derive statuses on demand.

Faster to ship, but less auditable.

Recommendation:

- short term: Option B
- medium term: Option A

---

## Suggested Implementation Sequence

### Phase 0. Freeze Frontend Contract

Before writing backend code, finalize the JSON response shapes for:

- `/signals`
- `/symbols`
- `/history`
- `/benchmark`
- `/insights`

Reason:

- avoid frontend churn
- keep mock-to-real migration simple

### Phase 1. Replace Mock Chart Data

Deliver:

- `GET /history`
- `GET /benchmark`

Frontend change:

- replace `mockMarket.js` series data for chart with API calls
- keep existing UI and time-range toggles

Acceptance criteria:

- default page loads real NIFTY history
- selecting `RELIANCE` shows real OHLC candles
- day/month/year buttons fetch correct range data

### Phase 2. Replace Symbol Search/Deck

Deliver:

- `GET /symbols`

Frontend change:

- replace static symbol list with backend-backed search and deck

Acceptance criteria:

- search returns symbols from real backend data
- selected symbol persists in UI state

### Phase 3. Replace 7-Method Mock Panel

Deliver:

- `GET /insights`

Frontend change:

- replace mock strategy cards with real strategy diagnostics

Acceptance criteria:

- clicking `RELIANCE` shows real strategy statuses
- panel shows regime, latest model output, and latest strategy statuses

### Phase 4. Unify Live Signal Flow

Deliver:

- continue using existing `/signals`
- optionally add `GET /signals?symbol=RELIANCE`

Frontend change:

- selected symbol filters the live signal list or highlights matching entries

Acceptance criteria:

- symbol drilldown shows relevant live alerts without manual scanning

### Phase 5. Add Resilience

Deliver:

- loading states
- error states
- empty states
- stale-data timestamps

Frontend change:

- panels fail independently
- chart failure does not blank page

Acceptance criteria:

- one endpoint failing does not kill the full dashboard

---

## Backend Changes Required

## 1. Signal Service Should Gain Read APIs

Modify:

- `services/signal-service/app/main.py`

Add endpoints:

- `GET /symbols`
- `GET /history`
- `GET /benchmark`
- `GET /insights`

### Why signal-service first

- already has DB session setup
- already owns strategy concepts
- already already serves frontend-facing signals
- least friction

## 2. Add Read Schemas

Add new schema file, for example:

- `services/signal-service/app/schemas/market.py`

Define response models for:

- symbol list
- history candle
- benchmark
- insight response
- strategy status card

## 3. Add Data Access Layer

Add service module, for example:

- `services/signal-service/app/services/market_data.py`

Responsibilities:

- query `ohlcv_enriched`
- map frontend time ranges to DB windows
- aggregate symbol list
- load latest symbol state
- optionally fallback to parquet

## 4. Add Strategy Insight Aggregator

Add service module, for example:

- `services/signal-service/app/services/insights.py`

Responsibilities:

- fetch latest symbol feature row
- derive or load strategy states
- optionally call `model-service` for fresh prediction
- normalize into frontend-friendly payload

## 5. Optional: Add Benchmark Loader

If NIFTY benchmark is not already stored, add one explicit ingestion path.

Possible file:

- `scripts/ingest_nifty50.py`

If benchmark is already available elsewhere, reuse it, but do not hide the source.

---

## Frontend Changes Required

## 1. Introduce API Layer

Create:

- `frontend/src/api/market.js`

Functions:

- `fetchSignals()`
- `fetchSymbols(query)`
- `fetchHistory(symbol, range)`
- `fetchBenchmark(range)`
- `fetchInsights(symbol)`

This keeps fetch logic out of components.

## 2. Replace `mockMarket.js`

Current file:

- `frontend/src/mockMarket.js`

Plan:

- keep only as temporary fallback during migration
- remove after real APIs are in place

## 3. Update App State Model

Current main state already supports:

- `selectedSymbol`
- `timeRange`
- `signals`
- `query`

That state model is fine.

What changes:

- benchmark data becomes fetched
- symbol deck becomes fetched
- chart history becomes fetched
- insight panel becomes fetched

## 4. Add Panel-Level Fetching

Recommended fetch ownership:

- top benchmark card and default chart: benchmark query
- symbol deck: symbols query
- chart panel: history query
- strategy panel: insights query
- signals panel: signals query

Do not use one giant fetch for the whole page.

## 5. Add Loading and Error Boundaries Per Panel

Each section should independently render:

- loading
- success
- empty
- error

This is critical to avoid another blank-page experience.

---

## Query and Caching Strategy

Recommended cadence:

- `/signals`: every 5 seconds
- `/insights`: on symbol change, optionally refresh every 15 to 30 seconds
- `/history`: on symbol or range change only
- `/symbols`: debounce search input by 200 to 300 ms
- `/benchmark`: on load and every 30 to 60 seconds

If a data-fetch library is introduced later, use:

- React Query or SWR

For now, plain fetch is acceptable if kept inside an API module.

---

## Mapping Frontend Time Ranges To Backend

Frontend labels:

- `1D`
- `1M`
- `1Y`

Recommended backend mapping:

- `1D` -> last trading day intraday candles, interval `1m` or `5m`
- `1M` -> last 30 calendar days, interval `1d`
- `1Y` -> last 365 calendar days, interval `1wk` or `1d`

Important:

- backend should own the true interval mapping
- frontend should pass only a semantic range

---

## Database Considerations

### Existing confirmed tables

- `strategy_signals`
- `trade_signals`
- `ohlcv_enriched` via ingestion script

### Recommended indexes

For integration performance, ensure indexes exist on:

- `ohlcv_enriched(symbol, timestamp)`
- `trade_signals(symbol, timestamp)`
- `strategy_signals(symbol, timestamp, strategy_name)`

### Why this matters

The frontend will repeatedly query:

- latest row for a symbol
- recent history for a symbol
- recent signals for a symbol

Without indexes, the dashboard will feel slow.

---

## Data Quality Gaps To Resolve

### 1. Real NIFTY Benchmark Source

Status:

- not exposed today
- not confirmed as stored in backend tables

Impact:

- benchmark chart cannot be real until source is explicit

### 2. Strategy Status Persistence

Status:

- current backend persists triggered strategy rows, not full evaluation state

Impact:

- 7-method panel cannot be fully authoritative yet

### 3. Symbol Metadata

Status:

- company labels and sectors may not be uniformly available from current read paths

Impact:

- search results and symbol cards may need a static metadata mapping initially

### 4. Regime Accuracy

Status:

- current regime classifier is simplified

Impact:

- frontend should present strategy/regime outputs as current-system outputs, not institutional truth

---

## Testing Plan

## Backend Tests

At minimum validate:

1. `/symbols` returns expected symbols
2. `/history` returns sorted candles for a symbol
3. `/benchmark` returns benchmark payload
4. `/insights` returns exactly 7 strategy rows
5. `/signals` remains backward-compatible

## Frontend Tests

At minimum validate:

1. dashboard loads without blank page if one endpoint fails
2. changing symbol updates chart and insights
3. changing range updates chart
4. search filters symbol deck correctly
5. clicking a live signal selects that symbol

## Manual Validation

Manually validate these flows:

1. open dashboard -> NIFTY benchmark loads
2. search `RELIANCE` -> select -> chart updates
3. switch `1D` to `1M` -> candles update
4. strategy panel shows 7 entries
5. live signal click syncs selected symbol

---

## Rollout Plan

### Step 1

Implement backend read schemas and `/history`, `/symbols`

### Step 2

Connect frontend chart and symbol deck to those APIs

### Step 3

Implement `/insights`

### Step 4

Connect strategy panel and symbol detail panel

### Step 5

Implement `/benchmark`

### Step 6

Remove `mockMarket.js`

### Step 7

Add resilience, caching, and performance tuning

---

## Final Recommendation

The right immediate move is not a full new microservice. The right move is:

1. extend `signal-service` with frontend read APIs
2. use PostgreSQL `ohlcv_enriched` as the primary chart data source
3. keep `model-service` prediction-only
4. gradually replace frontend mocks endpoint by endpoint

This gets the dashboard integrated fastest while staying aligned with the backend that already exists.

After the read APIs stabilize, split them into a dedicated `data-service` only if load, ownership, or latency makes that necessary.

