# Paper Trading Implementation Blueprint

Date: 2026-04-11

Purpose:

This is the implementation-ready version of the paper trading plan. It is meant to reduce ambiguity during development by specifying:

- exact architecture choices
- required tables
- endpoint contracts
- frontend changes
- status flows
- failure handling
- rollout order
- file-level mapping in your repo
- source references from your friend's repo

This file does not change your application code. It is a build blueprint.

## 1. Goal

Add a paper trading execution path to your current system so that:

1. a trade alert appears in frontend
2. user clicks `Paper Buy` or `Paper Short`
3. system creates a paper order
4. system simulates execution
5. system records fills
6. system updates positions and PnL
7. frontend shows:
   - order history
   - fill history
   - open positions
   - realized/unrealized PnL

## 2. Do Not Start With A Full Kafka Rewrite

Your current architecture is:

- HTTP gateway
- FastAPI services
- Postgres-backed reads/writes
- React frontend

That means the fastest correct implementation is:

- build paper trading as one new service
- use synchronous DB-backed execution first
- optionally move to Kafka later

This is important because your friend's repo is execution-first and Kafka-first, while your repo is advisory-first and UI-first.

## 3. What To Reuse From Friend Repo

These are design sources, not copy-paste targets.

### OMS and lifecycle

Friend source:

- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/execution/oms.py`

Use for:

- state transition rules
- idempotency
- order audit trail

### Paper execution

Friend sources:

- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/execution/paper_gateway.py`
- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/execution/paper_gateway_matcher.py`
- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/execution/ems_paper.py`

Use for:

- fill simulation
- slippage
- immediate/near-immediate fills
- optional matcher-based realism later

### Position / PnL

Friend sources:

- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/accounting/position_tracker.py`
- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/execution/accounting_pnl.py`

Use for:

- fill-derived positions
- realized PnL
- unrealized PnL using latest price

### Exit automation

Friend sources:

- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/execution/exit_engine.py`
- `https://github.com/SreemukhMantripragada/trading-platform/blob/main/execution/stop_target_engine.py`

Use for:

- EOD flatten
- stop-loss and target-based auto exits

## 4. Integration Principle For Your Repo

Keep your current advisory pipeline intact.

Current:

`signal-service -> trade_signals -> gateway -> frontend`

Add:

`frontend action -> paper-trading-service -> paper_orders / paper_fills / paper_positions -> gateway -> frontend`

That means:

- `trade_signals` remains advisory-only
- `paper_orders` becomes user-action state
- `paper_fills` becomes execution truth
- `paper_positions` becomes holdings truth

Do not merge signal rows with order rows.

## 5. New Service To Add

Create:

- `services/paper-trading-service/app/main.py`
- `services/paper-trading-service/app/models/database.py`
- `services/paper-trading-service/app/models/schema.py`
- `services/paper-trading-service/app/schemas/paper.py`
- `services/paper-trading-service/app/services/oms.py`
- `services/paper-trading-service/app/services/price_resolver.py`
- `services/paper-trading-service/app/services/fill_simulator.py`
- `services/paper-trading-service/app/services/position_service.py`
- `services/paper-trading-service/app/services/pnl_service.py`
- `services/paper-trading-service/requirements.txt`

## 6. Gateway Changes

Your gateway currently routes:

- `/signals`
- `/symbols`
- `/history`
- `/benchmark`
- `/insights`
- `/predict`
- `/news`
- `/fundamentals`
- `/institutional-flow`
- `/sentiment`
- `/ai-analyze`

Current file:

- [gateway/main.py](/home/sumanth/Desktop/trading-system/gateway/main.py:1)

Add service URL:

- `"paper": "http://127.0.0.1:7012"`

Add routes:

- `POST /paper/orders`
- `POST /paper/orders/{client_order_id}/cancel`
- `POST /paper/orders/{client_order_id}/close`
- `GET /paper/orders`
- `GET /paper/fills`
- `GET /paper/positions`
- `GET /paper/pnl`
- `GET /paper/portfolio`
- `GET /paper/positions/{symbol}`

## 7. Database Design

## 7.1 Tables

### `paper_orders`

Purpose:

- source of truth for trader paper actions and OMS state

Suggested columns:

```sql
CREATE TABLE IF NOT EXISTS paper_orders (
  id SERIAL PRIMARY KEY,
  client_order_id VARCHAR(100) UNIQUE NOT NULL,
  trade_signal_id INTEGER NULL,
  parent_client_order_id VARCHAR(100) NULL,
  symbol VARCHAR(30) NOT NULL,
  side VARCHAR(10) NOT NULL,
  qty INTEGER NOT NULL,
  requested_price DOUBLE PRECISION NULL,
  filled_qty INTEGER NOT NULL DEFAULT 0,
  avg_fill_price DOUBLE PRECISION NULL,
  order_type VARCHAR(20) NOT NULL DEFAULT 'MARKET',
  strategy_name VARCHAR(100) NULL,
  regime VARCHAR(50) NULL,
  source VARCHAR(30) NOT NULL DEFAULT 'frontend',
  status VARCHAR(30) NOT NULL,
  note TEXT NULL,
  extra JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `paper_order_audit`

Purpose:

- status history

```sql
CREATE TABLE IF NOT EXISTS paper_order_audit (
  id SERIAL PRIMARY KEY,
  client_order_id VARCHAR(100) NOT NULL,
  from_status VARCHAR(30) NULL,
  to_status VARCHAR(30) NOT NULL,
  note TEXT NULL,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `paper_fills`

Purpose:

- execution truth

```sql
CREATE TABLE IF NOT EXISTS paper_fills (
  id SERIAL PRIMARY KEY,
  client_order_id VARCHAR(100) NOT NULL,
  symbol VARCHAR(30) NOT NULL,
  side VARCHAR(10) NOT NULL,
  qty INTEGER NOT NULL,
  price DOUBLE PRECISION NOT NULL,
  fees DOUBLE PRECISION NOT NULL DEFAULT 0,
  slippage_bps DOUBLE PRECISION NOT NULL DEFAULT 0,
  venue VARCHAR(20) NOT NULL DEFAULT 'PAPER',
  extra JSONB NOT NULL DEFAULT '{}'::jsonb,
  timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `paper_positions`

Purpose:

- current net position by symbol

```sql
CREATE TABLE IF NOT EXISTS paper_positions (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(30) UNIQUE NOT NULL,
  net_qty INTEGER NOT NULL DEFAULT 0,
  avg_price DOUBLE PRECISION NOT NULL DEFAULT 0,
  realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
  last_price DOUBLE PRECISION NULL,
  unrealized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `paper_daily_pnl`

Purpose:

- EOD or periodic snapshots

```sql
CREATE TABLE IF NOT EXISTS paper_daily_pnl (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(30) NOT NULL,
  trading_date DATE NOT NULL,
  realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
  unrealized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
  mtm_price DOUBLE PRECISION NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  UNIQUE(symbol, trading_date)
);
```

## 7.2 Indexes

Add indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol_created
ON paper_orders(symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_paper_orders_status
ON paper_orders(status);

CREATE INDEX IF NOT EXISTS idx_paper_fills_symbol_ts
ON paper_fills(symbol, timestamp DESC);
```

## 8. Order Lifecycle

Use these statuses:

- `NEW`
- `ACK`
- `PARTIAL`
- `FILLED`
- `CANCELED`
- `REJECTED`
- `CLOSE_REQUESTED`

Valid transitions:

- `NEW -> ACK`
- `NEW -> REJECTED`
- `ACK -> PARTIAL`
- `ACK -> FILLED`
- `ACK -> CANCELED`
- `PARTIAL -> FILLED`
- `PARTIAL -> CANCELED`
- `FILLED -> CLOSE_REQUESTED` for derived close workflow only

Do not allow invalid transitions.

## 9. Execution Model For Phase 1

## 9.1 Fill logic

Use latest close from:

- `ohlcv_enriched.close`

Price resolution order:

1. get latest `close` for symbol from `ohlcv_enriched`
2. if no row exists, reject order
3. apply slippage:
   - buy: `price * (1 + slippage_bps / 10000)`
   - short/sell: `price * (1 - slippage_bps / 10000)`
4. optionally wait `fill_latency_ms`
5. insert fill
6. update order
7. update positions

## 9.2 Suggested defaults

- `slippage_bps = 5`
- `fill_latency_ms = 100`
- `order_type = MARKET`
- `fees = 0` initially, then configurable

## 9.3 Qty rules

For phase 1:

- accept qty from frontend, or
- default qty = 1 for simplest path, or
- derive qty from fixed capital per trade

Best simple approach:

- add `paper_qty` selector in UI
- default `qty = 1`

Do not bring broker-style sizing complexity into version 1.

## 10. Position and PnL Rules

## 10.1 Position model

Track one net position per symbol.

For BUY fills:

- increase `net_qty`
- recalculate `avg_price`

For SELL fills against long:

- reduce `net_qty`
- realize pnl on closed quantity

For SHORT entry:

- represent as negative `net_qty`
- use average entry price for short

For BUY against short:

- reduce negative exposure
- realize pnl accordingly

## 10.2 Realized PnL

Long close:

- `(sell_price - avg_price) * closed_qty - fees`

Short close:

- `(avg_price - buy_price) * closed_qty - fees`

## 10.3 Unrealized PnL

Long open:

- `(last_price - avg_price) * net_qty`

Short open:

- `(avg_price - last_price) * abs(net_qty)`

## 11. API Contracts

## 11.1 Create paper order

`POST /paper/orders`

Request:

```json
{
  "trade_signal_id": 123,
  "symbol": "RELIANCE",
  "side": "BUY",
  "qty": 1,
  "requested_price": 2968.20,
  "strategy_name": "ORB",
  "regime": "Trending",
  "extra": {
    "stop_loss": 2949.10,
    "target_l1": 2984.10,
    "target_l2": 2998.20,
    "target_l3": 3021.50,
    "probability": 0.78,
    "confidence": 0.82
  }
}
```

Response:

```json
{
  "status": "success",
  "data": {
    "client_order_id": "PAPER-1712839200-RELIANCE-BUY",
    "order_status": "FILLED",
    "symbol": "RELIANCE",
    "side": "BUY",
    "qty": 1,
    "fill_price": 2970.68,
    "filled_at": "2026-04-11T10:35:00+05:30"
  },
  "error": null
}
```

## 11.2 Orders list

`GET /paper/orders?symbol=RELIANCE&limit=50`

## 11.3 Fills list

`GET /paper/fills?symbol=RELIANCE&limit=50`

## 11.4 Positions

`GET /paper/positions`

Response:

```json
{
  "status": "success",
  "data": [
    {
      "symbol": "RELIANCE",
      "net_qty": 2,
      "avg_price": 2970.68,
      "last_price": 2981.20,
      "realized_pnl": 120.5,
      "unrealized_pnl": 21.04
    }
  ],
  "error": null
}
```

## 11.5 PnL summary

`GET /paper/pnl`

Response:

```json
{
  "status": "success",
  "data": {
    "realized_pnl": 840.25,
    "unrealized_pnl": -95.75,
    "open_positions": 4,
    "closed_trades": 12
  },
  "error": null
}
```

## 11.6 Close order

`POST /paper/orders/{client_order_id}/close`

Behavior:

- resolves open quantity for symbol
- creates reverse-side order
- fills it
- updates positions/pnl

## 12. Backend File-Level Mapping In Your Repo

## 12.1 Current signal sources

Relevant files:

- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:71)
- [services/signal-service/app/models/schema.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/models/schema.py:17)
- [services/signal-service/app/schemas/signal.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/schemas/signal.py:8)

Implementation note:

- `trade_signals.id` should become optional source linkage for `paper_orders.trade_signal_id`

## 12.2 Current frontend touchpoints

Relevant files:

- [frontend/src/components/SignalCard.tsx](/home/sumanth/Desktop/trading-system/frontend/src/components/SignalCard.tsx:1)
- [frontend/src/components/SignalsGallery.tsx](/home/sumanth/Desktop/trading-system/frontend/src/components/SignalsGallery.tsx:1)
- [frontend/src/pages/StockPage.tsx](/home/sumanth/Desktop/trading-system/frontend/src/pages/StockPage.tsx:1)
- [frontend/src/api/market.ts](/home/sumanth/Desktop/trading-system/frontend/src/api/market.ts:1)
- [frontend/src/types/market.ts](/home/sumanth/Desktop/trading-system/frontend/src/types/market.ts:1)

Implementation note:

- `SignalCard` is the best place to add `Paper Buy` and `Paper Short`
- `StockPage` is the best place to show symbol-specific paper positions
- add a dedicated `/paper-portfolio` route for full paper account view

## 13. Frontend Detailed Plan

## 13.1 New types

Add to [frontend/src/types/market.ts](/home/sumanth/Desktop/trading-system/frontend/src/types/market.ts:1):

```ts
export interface PaperOrder {
  client_order_id: string;
  trade_signal_id?: number;
  symbol: string;
  side: 'BUY' | 'SELL' | 'SHORT';
  qty: number;
  requested_price?: number;
  avg_fill_price?: number;
  status: string;
  strategy_name?: string;
  regime?: string;
  created_at: string;
  updated_at?: string;
}

export interface PaperFill {
  id: number;
  client_order_id: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  fees: number;
  timestamp: string;
}

export interface PaperPosition {
  symbol: string;
  net_qty: number;
  avg_price: number;
  last_price?: number;
  realized_pnl: number;
  unrealized_pnl: number;
  updated_at?: string;
}

export interface PaperPnlSummary {
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions: number;
  closed_trades: number;
}
```

## 13.2 New API methods

Add to [frontend/src/api/market.ts](/home/sumanth/Desktop/trading-system/frontend/src/api/market.ts:1):

- `createPaperOrder(payload)`
- `closePaperOrder(clientOrderId)`
- `fetchPaperOrders(symbol?)`
- `fetchPaperFills(symbol?)`
- `fetchPaperPositions()`
- `fetchPaperSymbolPosition(symbol)`
- `fetchPaperPnl()`
- `fetchPaperPortfolio()`

## 13.3 Signal card actions

Update [frontend/src/components/SignalCard.tsx](/home/sumanth/Desktop/trading-system/frontend/src/components/SignalCard.tsx:1):

Add:

- `Paper Buy`
- `Paper Short`

Action logic:

- if signal direction is `BUY`, primary CTA should be `Paper Buy`
- if signal direction is `SHORT`, primary CTA should be `Paper Short`
- optional secondary CTA for taking contrarian/manual side later, but not in V1

Best initial behavior:

- show one button that matches signal direction

## 13.4 Dashboard changes

Update [frontend/src/App.tsx](/home/sumanth/Desktop/trading-system/frontend/src/App.tsx:1):

Add:

- top summary card:
  - `Paper PnL`
- new section below signals:
  - `Open Paper Positions`
- recent fills strip or table

## 13.5 Stock page changes

Update [frontend/src/pages/StockPage.tsx](/home/sumanth/Desktop/trading-system/frontend/src/pages/StockPage.tsx:1):

Add two panels:

1. `Paper Position`
- net qty
- avg price
- last price
- realized pnl
- unrealized pnl
- `Close Position` button

2. `Paper Order History`
- latest orders and fills for that symbol

## 13.6 Dedicated route

Add route:

- `/paper-portfolio`

Contents:

- summary cards
- open positions table
- order history table
- fills table
- pnl summary

## 14. OMS Service Behavior

## 14.1 `oms.py`

Methods:

- `create_order()`
- `transition_order()`
- `append_audit()`
- `get_order()`
- `list_orders()`

Responsibilities:

- generate `client_order_id`
- reject invalid transitions
- ensure idempotent creation if same request is retried

## 14.2 Suggested order ID format

```text
PAPER-{unix_ts}-{symbol}-{side}-{random_suffix}
```

Example:

```text
PAPER-1712839200-RELIANCE-BUY-X3A9
```

## 15. Pricing / Fill Simulator

## 15.1 `price_resolver.py`

Methods:

- `get_latest_close(symbol)`
- `get_latest_bar(symbol)`

Source:

- `ohlcv_enriched`

## 15.2 `fill_simulator.py`

Methods:

- `simulate_market_fill(symbol, side, qty, requested_price=None)`

Returns:

- `fill_price`
- `slippage_bps`
- `fees`
- `fill_latency_ms`

## 15.3 Advanced behavior later

After V1:

- price capping against bar high/low
- intraday liquidity buckets
- different slippage for long/short
- partial fills

Do not add partial fills in V1 unless needed.

## 16. Position Service

## 16.1 `position_service.py`

Methods:

- `apply_fill(fill)`
- `refresh_symbol_position(symbol)`
- `refresh_all_positions()`
- `close_symbol_position(symbol)`

## 16.2 Important nuance: short positions

You currently use signal directions like:

- `BUY`
- `SHORT`

Standardize for orders:

- use `BUY` and `SELL`

Meaning:

- opening a short should be represented as `SELL`
- closing a short should be represented as `BUY`

But UI can still say `SHORT` for clarity.

This matters because PnL logic becomes cleaner.

## 17. Exit Logic

## 17.1 Version 1

Only support:

- manual close
- optional EOD flatten script/job

## 17.2 Version 2

Support:

- stop loss exits
- target exits
- maybe partial target booking

## 17.3 Where to store stop/target

Store inside `paper_orders.extra`:

```json
{
  "stop_loss": 2949.10,
  "target_l1": 2984.10,
  "target_l2": 2998.20,
  "target_l3": 3021.50
}
```

Later an exit engine can scan those values against latest price.

## 18. Error Handling And Edge Cases

These are important. Do not skip them.

### 18.1 Duplicate button clicks

Problem:

- user clicks `Paper Buy` twice

Solution:

- disable button while request is in flight
- backend should support idempotency token or duplicate detection

### 18.2 Missing price row

Problem:

- no current `ohlcv_enriched` row for symbol

Solution:

- reject order with `REJECTED`
- return clear error

### 18.3 Signal stale but user still clicks

Problem:

- signal from old timestamp is executed much later

Solution:

- store `signal_timestamp`
- return warning flag if signal is older than threshold
- still allow paper execution if desired

### 18.4 Frontend-visible status

Problem:

- order succeeded but user cannot tell if it filled

Solution:

- return immediate order result
- refresh orders/fills/positions after create call

### 18.5 Position flip

Problem:

- user is long and clicks short

Solution:

Initial rule:

- reject opposite-side entry if open position exists

Better later:

- allow flatten + reverse in one flow

### 18.6 Manual close with no position

Solution:

- return no-op or validation error

### 18.7 EOD flatten vs manual close race

Solution:

- lock symbol position row or use transaction-safe close logic

## 19. Security / Safety Rules

Even for paper trading:

- validate symbol
- validate qty > 0
- validate side
- validate no invalid state transition
- never update position directly from frontend
- only fills should mutate position state

## 20. Rollout Plan

## Milestone A - backend foundations

- create DB tables
- create paper service
- implement OMS
- implement synchronous fill simulator
- implement positions/PnL reads

Done when:

- API can create order and return filled response
- DB contains order, fill, position rows

## Milestone B - frontend actions

- add paper trade button to signal card
- add stock-page paper position panel
- add dashboard paper summary

Done when:

- user can execute paper trade from UI and see it immediately

## Milestone C - portfolio screen

- add `/paper-portfolio`
- show positions, pnl, orders, fills

## Milestone D - exits

- add close position button
- add EOD flatten
- add stop/target auto exits later

## 21. Nice-To-Have Enhancements Later

- Kafka event flow for orders and fills
- Prometheus metrics for paper service
- Grafana dashboard
- Dockerized startup
- multi-user paper accounts
- per-strategy paper analytics
- trade journal notes

## 22. Suggested Exact Implementation Order

1. Add DB schema.
2. Add `paper-trading-service`.
3. Add gateway routes.
4. Add `createPaperOrder` frontend API.
5. Add button in `SignalCard`.
6. Add paper position panel on stock page.
7. Add paper portfolio route.
8. Add manual close.
9. Add EOD flatten.
10. Add stop/target automation.

## 23. What Not To Do

- do not copy your friend's entire execution stack as-is
- do not add Kafka before V1 works
- do not merge advisory signals and executed orders into same table
- do not let frontend compute PnL
- do not skip order audit trail
- do not skip short-side handling rules

## 24. Final Build Decision

If implementation starts now, the best practical architecture is:

### V1

- HTTP-triggered paper order creation
- DB-backed fill simulation
- frontend visibility for orders/fills/positions/pnl

### V2

- exit engine
- better slippage / fees
- EOD flatten

### V3

- Kafka integration
- Docker / observability
- stronger OMS sophistication

That is the shortest path from your current repo to a usable paper trading workflow.
