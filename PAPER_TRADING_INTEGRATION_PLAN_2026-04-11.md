# Paper Trading Integration Plan

Date: 2026-04-11

Goal:

Bring paper-trade execution into this project using the best ideas from your friend's repo, while keeping your current advisory + frontend architecture. Paper trades must be visible in the frontend.

Important constraint:

- Do not do a full Kafka rewrite first.
- First build a minimal paper-execution path that fits your current services.
- Borrow the design from your friend's OMS/paper/fills/positions flow, not the entire infrastructure at once.

## Target Outcome

Current flow:

`market data -> features -> model -> signal -> trade alert -> frontend`

Target flow:

`market data -> features -> model -> signal -> trade alert -> trader clicks paper buy/short -> OMS -> paper execution -> fills -> positions/PnL -> frontend`

## What To Borrow From Friend Repo

Borrow the concepts, not a blind copy.

### 1. OMS concept

From friend repo:

- `/tmp/friend-trading-platform/execution/oms.py`

Use in your project:

- create one source of truth for order lifecycle
- every paper trade request gets a unique `client_order_id`
- state transitions:
  - `NEW`
  - `ACK`
  - `FILLED`
  - `PARTIAL`
  - `CANCELED`
  - `REJECTED`

### 2. Paper gateway concept

From friend repo:

- `/tmp/friend-trading-platform/execution/paper_gateway.py`
- `/tmp/friend-trading-platform/execution/paper_gateway_matcher.py`
- `/tmp/friend-trading-platform/execution/ems_paper.py`

Use in your project:

- simulate fills from latest market price
- apply configurable slippage
- optional delay
- create fill records
- update order state
- update positions

### 3. Position and PnL tracking concept

From friend repo:

- `/tmp/friend-trading-platform/accounting/position_tracker.py`
- `/tmp/friend-trading-platform/execution/accounting_pnl.py`

Use in your project:

- maintain open paper positions
- compute realized PnL
- compute unrealized PnL from latest close

### 4. Exit automation concept

From friend repo:

- `/tmp/friend-trading-platform/execution/exit_engine.py`
- `/tmp/friend-trading-platform/execution/stop_target_engine.py`

Use in your project:

- auto-close near EOD in paper mode
- later add stop-loss and target auto-exit logic

## Recommended Integration Strategy

## Phase 1 - Add Paper Trading Without Kafka

This is the correct first move for your repo.

Do not start with Kafka. Your current stack is HTTP + DB + frontend. Keep that shape and add a simple paper execution service.

### Backend design

Add a new service:

- `services/paper-trading-service/`

Responsibilities:

- accept paper order requests
- create OMS order record
- simulate execution
- create fill record
- update paper positions
- update paper pnl
- expose read APIs for frontend

### New database tables

Add these tables:

1. `paper_orders`
- `id`
- `client_order_id`
- `signal_id` or `trade_signal_id`
- `symbol`
- `side`
- `qty`
- `requested_price`
- `fill_price`
- `status`
- `strategy_name`
- `regime`
- `created_at`
- `updated_at`
- `extra`

2. `paper_fills`
- `id`
- `client_order_id`
- `symbol`
- `side`
- `qty`
- `price`
- `fees`
- `slippage_bps`
- `timestamp`

3. `paper_positions`
- `id`
- `symbol`
- `net_qty`
- `avg_price`
- `realized_pnl`
- `updated_at`

4. `paper_position_snapshots` or `paper_pnl_snapshots`
- `id`
- `symbol`
- `unrealized_pnl`
- `realized_pnl`
- `mtm_price`
- `timestamp`

5. `paper_order_audit`
- `id`
- `client_order_id`
- `from_status`
- `to_status`
- `note`
- `meta`
- `timestamp`

### New backend endpoints

Add paper APIs behind gateway:

#### Trade actions

- `POST /paper/orders`
  Create a paper order from a selected trade alert.

- `POST /paper/orders/{client_order_id}/cancel`
  Cancel if still cancelable.

#### Reads for frontend

- `GET /paper/orders`
  Recent paper orders.

- `GET /paper/fills`
  Recent fills.

- `GET /paper/positions`
  Open paper positions.

- `GET /paper/pnl`
  Summary and symbol-level PnL.

- `GET /paper/portfolio`
  Combined view for UI convenience.

### Execution model for Phase 1

Simple synchronous fill model:

1. user clicks paper buy/short in frontend
2. gateway calls paper-trading-service
3. service creates `NEW` order
4. service marks `ACK`
5. service fetches latest symbol price from `ohlcv_enriched`
6. service applies paper slippage
7. service inserts fill
8. service marks order `FILLED`
9. service updates `paper_positions`
10. service returns execution result

This is enough for Monday-level controlled testing.

## Phase 2 - Frontend Trade Visibility

This must be built with the first paper-execution release, not later.

## UI changes required

### 1. Signal card actions

In the dashboard and stock page, every live alert should have:

- `Paper Buy`
- `Paper Short`
- maybe `Skip`

These actions should call `POST /paper/orders`.

### 2. New frontend types

Extend frontend types beyond current `Signal` model in:

- [frontend/src/types/market.ts](/home/sumanth/Desktop/trading-system/frontend/src/types/market.ts:1)

Add:

- `PaperOrder`
- `PaperFill`
- `PaperPosition`
- `PaperPnlSummary`

### 3. New frontend API functions

Extend:

- [frontend/src/api/market.ts](/home/sumanth/Desktop/trading-system/frontend/src/api/market.ts:1)

Add:

- `createPaperOrder`
- `fetchPaperOrders`
- `fetchPaperFills`
- `fetchPaperPositions`
- `fetchPaperPnl`
- `fetchPaperPortfolio`

### 4. Dashboard visibility

Add one new section on main dashboard:

- `Paper Trades`

Show:

- open positions count
- total realized pnl
- total unrealized pnl
- latest fills

### 5. Stock page visibility

Add one new panel in:

- [frontend/src/pages/StockPage.tsx](/home/sumanth/Desktop/trading-system/frontend/src/pages/StockPage.tsx:1)

Show for current symbol:

- open paper quantity
- avg price
- realized pnl
- unrealized pnl
- recent paper orders
- recent fills

### 6. Dedicated Paper Portfolio page

Add one route:

- `/paper-portfolio`

This page should show:

- current open positions
- order history
- fill history
- pnl summary
- EOD closed trades

This is better than trying to overload the existing stock page only.

## Phase 3 - Add Exit Logic

Once Phase 1 and 2 are stable:

### Add auto-exit support

Use your existing trade alert data:

- entry
- stop_loss
- target_l1
- target_l2
- target_l3

Recommended paper rules:

1. EOD flatten rule
- close all paper positions near market close

2. Stop loss rule
- if current price breaches stop, create exit paper order

3. Partial target rule
- optional later
- book 40/40/20 or your own target sizing model

Do not add partial exits on day 1 unless your order/fill model is already stable.

## Phase 4 - Add OMS Quality Features

After the basic paper flow works:

- idempotent order creation
- valid state transition rules
- cancel support
- retry-safe execution
- audit trail
- slippage and fee settings
- order rejection reasons
- per-user/trader session separation if needed

This is where your friend's OMS ideas should be adapted more deeply.

## Phase 5 - Optional Kafka Upgrade

Only do this after the non-Kafka version works.

Then move from:

- HTTP create order -> immediate fill

to:

- signal/OMS/order event -> Kafka -> paper execution consumer -> fill event -> position consumer -> UI read APIs

Suggested topics later:

- `paper_orders`
- `paper_fills`
- `paper_positions`
- `paper_pnl_updates`

But this is not required for the first usable version.

## Mapping Friend Repo Concepts To Your Repo

### Friend OMS -> Your new paper order service

Take from friend:

- order state machine
- audit trail
- idempotency

Do not copy directly:

- Kafka-only assumptions
- execution coupling to their existing orders table

### Friend paper gateway -> Your fill simulator

Take from friend:

- latest-price-based fill
- configurable slippage
- configurable delay

Do not copy directly:

- Kafka consumer dependency for phase 1

### Friend position tracker / pnl -> Your DB read model

Take from friend:

- positions derived from fills
- MTM via latest bar close

Do not copy directly:

- their exact table assumptions

## Concrete Build Plan

## Step 1 - Schema

Create migration/init for:

- `paper_orders`
- `paper_fills`
- `paper_positions`
- `paper_order_audit`
- optional `paper_pnl_snapshots`

## Step 2 - New service

Create:

- `services/paper-trading-service/app/main.py`
- `services/paper-trading-service/app/models/`
- `services/paper-trading-service/app/schemas/`
- `services/paper-trading-service/app/services/`

Service modules:

- `oms.py`
- `price_resolver.py`
- `fill_simulator.py`
- `position_updater.py`
- `pnl_service.py`

## Step 3 - Gateway integration

Update:

- [gateway/main.py](/home/sumanth/Desktop/trading-system/gateway/main.py:1)

Add routes:

- `/paper/orders`
- `/paper/fills`
- `/paper/positions`
- `/paper/pnl`
- `/paper/portfolio`

## Step 4 - Frontend action wiring

Update signal cards and stock page so a user can place paper trades.

Use current signal payload:

- symbol
- direction
- entry
- stop_loss
- targets
- probability
- confidence
- strategy

## Step 5 - Frontend portfolio visibility

Add:

- paper portfolio summary on dashboard
- symbol paper position card on stock page
- dedicated portfolio page

## Step 6 - Exit engine

Start with:

- manual close position button
- EOD flatten job

Then add:

- stop-loss auto close
- target auto close

## Data Source Rules

For paper execution price in Phase 1:

- use latest `ohlcv_enriched.close`

For better realism later:

- use latest minute high/low/open/close based fill rules
- add slippage by direction and liquidity bucket

## Minimum Viable UI

Paper trading is not complete unless the user can see:

1. order submitted
2. order filled
3. open position
4. running pnl
5. exit/close result

Minimum visible widgets:

- `Paper Portfolio Summary`
- `Recent Paper Orders`
- `Open Positions`
- `Recent Fills`

## Risks To Avoid

- Do not mix `trade_signals` and `paper_orders` into one table.
  Signals are opportunities. Orders are user actions.

- Do not let frontend write directly to signal tables.

- Do not add live broker execution before paper OMS is stable.

- Do not start with Kafka unless the HTTP version already works.

- Do not skip audit trail.

## Recommended Timeline

### Sprint 1

- DB schema
- paper-trading-service
- gateway routes
- create paper order
- immediate fill simulation
- paper positions API

### Sprint 2

- dashboard paper widgets
- stock page paper widgets
- paper portfolio page
- manual close position
- realized/unrealized PnL

### Sprint 3

- EOD flatten
- stop-loss auto exit
- audit improvements
- better slippage model

### Sprint 4

- Kafka/event-driven refactor if still needed
- Docker/Nginx integration
- observability and alerts

## Final Recommendation

Best approach:

- copy the execution model ideas from your friend
- do not copy the full Kafka architecture first
- build a clean `paper-trading-service` in your repo
- expose trades, fills, positions, and PnL through gateway
- make paper trades directly visible in the React frontend

That gives you the fastest path from:

- `signal advisory`

to:

- `paper-tradable advisory platform`
