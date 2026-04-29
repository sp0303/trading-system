# Nifty Elite Trading System

## End-to-End System Document

> **Motto**
>
> **Systematic Edge. Institutional Grade. Trader in Control.**

---

## 1. What This System Is

This is a multi-service intraday trading platform for Indian equities.

Its job is to:

- extract market data from Angel One
- transform that data into enriched technical features
- score market opportunities with a machine-learning ensemble
- generate filtered trade signals using strategy logic
- expose those signals through APIs and the frontend
- simulate order execution through a paper-trading stack
- track positions, cash, realized P&L, and unrealized P&L
- monitor the live pipeline with Kafka, Prometheus, Grafana, and Loki

In simple terms:

```text
Market Data -> Bars -> Features -> Models -> Strategies -> Signals -> Orders -> Positions -> P&L -> Monitoring
```

---

## 2. What We Are Doing

The system is designed to detect intraday opportunities from live and historical OHLCV data, then convert those opportunities into structured trade ideas.

Each trade idea contains:

- symbol
- direction
- entry
- stop loss
- target L1
- target L2
- target L3
- probability
- confidence
- regime

The current stack supports two practical modes:

### A. Advisory / dashboard mode

Signals are generated and displayed to the user through the gateway and frontend.

### B. Paper-trading mode

Orders are simulated, positions are updated, cash is debited or credited, and P&L is tracked without sending real broker orders.

---

## 3. Core Motto in System Terms

The motto is not branding only. It is reflected in the implementation:

- **Systematic Edge**: signals come from rules plus ML, not discretion
- **Institutional Grade**: Kafka, metrics, audit trails, and service separation are built in
- **Trader in Control**: the paper trading service is execution simulation, while the frontend and gateway remain the user-facing control layer

---

## 4. End-to-End Architecture

### User-facing services

| Service | Port | Purpose |
|---|---:|---|
| `gateway` | `8000` | single API entry point and frontend host |
| `frontend` | `3000` | dashboard, stock views, paper portfolio |
| `paper-trading-service` | `7012` | orders, fills, positions, account, daily P&L |

### Intelligence services

| Service | Port | Purpose |
|---|---:|---|
| `signal-service` | `7004` | regime logic, strategy execution, signal filtering |
| `model-service` | `7003` | ensemble prediction for probability, return, drawdown |
| `news-service` | `7007` | RSS-based market news |
| `fundamental-service` | `7008` | financial metrics |
| `institutional-service` | `7009` | institutional flow style metrics |
| `sentiment-service` | `7010` | headline sentiment scoring |
| `ai-service` | `7011` | thesis validation / AI commentary |

### Market data and pipeline services

| Layer | Purpose |
|---|---|
| `scripts/ingestion/angel_one_ws.py` | live tick extraction from Angel One to Kafka |
| `scripts/compute/bar_builder_1s.py` | `ticks -> bars.1s` |
| `scripts/compute/bar_aggregator_1m.py` | `bars.1s -> bars.1m` |
| `scripts/compute/live_enrichment.py` | `bars.1m -> ohlcv_enriched` |
| `services/signal-service/app/services/bar_consumer.py` | consumes `bars.1m`, calls signal engine |
| `scripts/sync_data.py` | historical backfill and feature sync |

---

## 5. Data Extraction

### Historical extraction

Historical extraction is handled by `scripts/sync_data.py`.

It:

1. logs into Angel One
2. checks the latest timestamp already stored in `ohlcv_enriched`
3. fetches only the missing candle gap
4. fetches index proxies like `NIFTYBEES` and `BANKBEES`
5. enriches the raw data with technical features
6. appends the result into PostgreSQL

This is an incremental sync, not a blind reload.

### Live extraction

Live extraction is handled by `scripts/ingestion/angel_one_ws.py`.

It:

1. logs into Angel One SmartWebSocket V2
2. dynamically discovers the trading universe from parquet-backed symbol files
3. subscribes to symbol tokens
4. receives live ticks
5. pushes normalized tick events to Kafka topic `ticks`

Each live tick message contains a compact payload like:

```json
{
  "symbol": "RELIANCE",
  "event_ts": 1714209300000000000,
  "ltp": 2941.25,
  "vol": 18234,
  "source": "angel"
}
```

---

## 6. Data Processing

The live stream is processed in stages.

### Stage 1: Tick to 1-second bars

`scripts/compute/bar_builder_1s.py` consumes Kafka topic `ticks` and produces:

- PostgreSQL table `bars_1s`
- Kafka topic `bars.1s`

Each symbol is aggregated into 1-second OHLCV bars.

### Stage 2: 1-second bars to 1-minute bars

`scripts/compute/bar_aggregator_1m.py` consumes `bars.1s` and produces:

- PostgreSQL table `bars_1m`
- Kafka topic `bars.1m`

This 1-minute candle is the main live trading bar used by the downstream signal system.

### Stage 3: live feature enrichment

`scripts/compute/live_enrichment.py` consumes `bars.1m`, maintains a recent history cache per symbol, and computes enriched features before upserting into `ohlcv_enriched`.

### Stage 4: signal trigger

`services/signal-service/app/services/bar_consumer.py` consumes `bars.1m`, fetches the latest enriched row for that symbol, and sends it to `signal-service /process`.

---

## 7. Feature Engineering

Feature engineering is centralized in [`shared/feature_engineer.py`](/home/sumanth/Desktop/trading-system/shared/feature_engineer.py).

The system computes price-action, time, volume, volatility, momentum, and market-context features, including:

- returns and log returns
- range and range percent
- VWAP and distance from VWAP
- volume spike ratio and volume z-score
- RSI
- MACD histogram
- ADX
- stochastic
- ATR
- Bollinger %B
- CMF
- OBV slope
- rolling volatility
- relative volume
- lagged returns and indicators
- fractional differentiation
- wavelet-denoised return
- Nifty-relative strength

The system guide describes this as roughly 70+ enriched features, and the code confirms a broad multi-factor feature set.

---

## 8. What We Are Predicting

The model service does not directly place trades. It predicts trade quality.

The current `model-service` outputs:

- `probability`
- `expected_return`
- `expected_drawdown`
- `confidence`
- `is_anomaly`
- `models_used`

In practice, the prediction stack is answering:

- How likely is this setup to work?
- If it works, how much upside is expected?
- If it fails or weakens, how much adverse movement is expected?
- Are the underlying models agreeing?
- Does this input look abnormal relative to training conditions?

---

## 9. How Prediction Works

The model stack lives in [`services/model-service/app/services/ensemble.py`](/home/sumanth/Desktop/trading-system/services/model-service/app/services/ensemble.py).

It loads:

- a scaler
- label encoders
- feature column definitions
- anomaly detector
- target-specific trained models

The model service predicts three targets:

- `target_prob`
- `target_mfe`
- `target_mae`

These map to:

- probability of success
- expected favorable excursion
- expected adverse excursion

The ensemble uses multiple model families and then a meta-model to aggregate them. The code explicitly whitelists artifacts such as:

- `logistic`
- `rf`
- `xgb`
- `lgbm`
- `cat`
- `nb`
- `ridge`
- `meta`

Confidence is computed from disagreement across the classifier members. Lower variance means higher confidence.

---

## 10. Signal Generation

The signal engine lives in [`services/signal-service/app/main.py`](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py).

Its live flow is:

```text
Enriched Features
   -> Market Regime Classifier
   -> Strategy Evaluation
   -> Model Prediction
   -> Raw Strategy Signal Logging
   -> Strict Signal Filter
   -> Target Calculation
   -> Trade Alert Creation
   -> Optional AI Validation (Currently DISABLED for performance)
   -> Optional Auto Paper / Kafka Order Submission
```

### Strategies currently wired in

- ORB
- VWAP Reversion
- Intraday Momentum
- Relative Strength
- Volatility Squeeze
- Volume Reversal
- Market Regime Classifier

### Regime policy currently applied

- `Trending`: ORB, Momentum, Relative Strength
- `Range-Bound`: VWAP Reversion, Volume Reversal, Relative Strength
- `Normal`: ORB, Momentum, VWAP Reversion, Vol Squeeze, Relative Strength

### Output of a successful signal

When a signal passes filtering, a `TradeSignal` record is created with:

- symbol
- direction
- entry
- stop loss
- target L1
- target L2
- target L3
- probability
- confidence
- regime
- status

That is the main artifact consumed by the dashboard.

---

## 11. How Orders Are Placed

There are **two different execution paths** in this repository, and it is important to keep them separate.

### Path A: direct paper OMS

This is the fully implemented paper-execution path.

The gateway exposes:

- `POST /paper/orders`
- `GET /paper/orders`
- `GET /paper/fills`
- `GET /paper/positions`
- `GET /paper/account`
- `GET /paper/daily-pnl`
- close-position endpoints

These routes proxy into `paper-trading-service`, where the OMS performs:

```text
NEW -> ACK -> FILLED
```

inside [`services/paper-trading-service/app/services/oms.py`](/home/sumanth/Desktop/trading-system/services/paper-trading-service/app/services/oms.py).

The sequence is:

1. create paper order
2. write audit row
3. acknowledge order
4. resolve latest market price
5. run risk validation
6. simulate fill with slippage
7. mark order as `FILLED`
8. write fill record
9. update position and account cash

### Path B: Kafka institutional order path

This path is partially implemented for institutional-style flow.

The signal service can auto-submit a `NEW` order to Kafka using `KafkaOrderClient`, and the execution risk manager consumes those orders, sizes them, and republishes approved orders to `orders.sized`.

That means the repo currently contains:

- Kafka order producer from signal service
- Kafka risk approval and sizing engine
- institutional OMS state transition logic

But in this repository snapshot, there is **no final consumer that turns `orders.sized` into a completed paper fill or real broker execution event**.

So:

- **direct paper trading is operational**
- **Kafka institutional execution is fully implemented**: Approved orders from `orders.sized` are now consumed and executed by the paper trading service.
- **the execution loop is closed** in this repo.

---

## 12. Paper Trading: Exact Balance Logic

The account is auto-seeded at startup with:

- `total_capital = 1,000,000`
- `available_cash = 1,000,000`

That is a 10 lakhs paper account, consistent with the institutional dashboard frontend.

### Cash deduction and addition

The balance logic is implemented in [`services/paper-trading-service/app/services/position_service.py`](/home/sumanth/Desktop/trading-system/services/paper-trading-service/app/services/position_service.py).

For every fill:

- `BUY` or `LONG` -> cash impact is negative
- `SELL` or `SHORT` -> cash impact is positive

Formula (including brokerage):

```text
total_cost = price * qty
brokerage = total_cost * 0.0005  (0.05% all-in flat rate)

BUY/LONG  -> available_cash -= (total_cost + brokerage)
SELL/SHORT -> available_cash += (total_cost - brokerage)
```

This means:

- opening a long reduces cash
- closing a long adds cash back
- opening a short increases cash immediately in the simulated ledger
- covering a short reduces cash

---

## 13. Position Updates

The paper position model stores:

- `symbol`
- `net_qty`
- `avg_price`
- `realized_pnl`
- `last_price`
- `unrealized_pnl`

### Same-side increase

If a position is increased in the same direction:

- net quantity increases
- average price is recalculated using weighted average

### Reduction or close

If a fill is against the existing position:

- the service computes how much quantity is being closed
- realized P&L is added to the position
- net quantity is reduced

### Direction flip

If the fill crosses through zero and flips direction:

- realized P&L is booked on the closed portion
- the new position starts with `avg_price = fill_price`

---

## 14. P&L Calculations

### Realized P&L

Realized P&L is booked when an opposing fill closes part or all of an existing position.

Formulas:

```text
Closing a long:
realized_pnl += (sell_price - avg_price) * closed_qty

Closing a short:
realized_pnl += (avg_price - buy_price) * closed_qty
```

### Unrealized P&L

Unrealized P&L is recalculated using the latest resolved market price.

Formulas:

```text
Long:
unrealized_pnl = (current_price - avg_price) * net_qty

Short:
unrealized_pnl = (avg_price - current_price) * abs(net_qty)
```

### Account summary logic

The `/account` endpoint computes:

- starting capital
- available cash
- invested capital
- market value
- unrealized P&L
- realized P&L
- total equity

Current total equity is returned as:

```text
total_equity = available_cash + market_value
```

The `/daily-pnl` endpoint summarizes:

- realized P&L
- unrealized P&L
- total P&L
- trades today
- open positions
- per-position breakdown

---

## 15. Risk Controls in Paper Trading

Paper order validation is enforced in [`services/paper-trading-service/app/services/risk_service.py`](/home/sumanth/Desktop/trading-system/services/paper-trading-service/app/services/risk_service.py).

Current controls include:

- max open positions
- max notional per trade
- max position notional
- minimum cash buffer
- optional pyramiding block
- optional direction-flip block

For long-side orders, the system also checks remaining cash after the order and rejects the order if the configured cash buffer would be violated.

---

## 16. Simulated Execution

The paper fill simulator applies:

- artificial latency
- slippage in basis points
- zero fees for now

Default behavior:

- `5 bps` slippage
- `100 ms` latency

Price resolution for fills and mark-to-market currently comes from the latest `close` in `ohlcv_enriched`.

---

## 17. Auto Exit Monitoring

The paper trading service runs a background monitor thread.

It:

1. scans open positions
2. finds the latest filled order for that symbol
3. reads stop-loss and target levels from the order `extra` payload
4. resolves the latest price
5. automatically closes the position if SL or TP is hit

This gives the paper account a basic position lifecycle without user intervention after entry.

Current implementation checks:

- long SL: `current_price <= stop_loss`
- long TP: `current_price >= target`
- short SL: `current_price >= stop_loss`
- short TP: `current_price <= target`

The current logic uses the first available target among `target_l1`, `target_l2`, `target_l3` as the take-profit trigger.

---

## 18. Kafka in the Current System

Kafka is the event backbone for the live institutional-style pipeline.

### Topics currently implied by code

- `ticks`
- `bars.1s`
- `bars.1m`
- `orders`
- `orders.sized`

### What Kafka is doing today

- transporting live ticks
- transporting computed bars
- triggering signal processing from fresh bars
- carrying new execution intents to the risk manager

### Kafka Institutional Pipeline Status

- **Status**: ✅ FULLY OPERATIONAL
- Orders sized by `execution-service` are published to `orders.sized`.
- `paper-trading-service` consumes `orders.sized` and executes them using the institutional fill simulator.
- All institutional fills are recorded in the shared database and reflected in the dashboard.

---

## 19. Grafana, Prometheus, and Loki

The infrastructure stack in [`infra/docker-compose.yml`](/home/sumanth/Desktop/trading-system/infra/docker-compose.yml) provisions:

- Kafka
- Kafka UI
- Redis
- PostgreSQL
- Prometheus
- Grafana
- Loki
- Promtail

### Prometheus metrics

Metrics are exposed by multiple services and scripts, including:

- tick intake metrics
- queue depth
- tick latency
- 1-second bar write/publish counts
- 1-minute bar write/publish counts
- signal request metrics
- model request metrics
- risk approval/rejection counts
- tradable equity

### Grafana dashboard

The bundled dashboard `Nifty Elite: Institutional Overview` currently visualizes:

- Angel One tick velocity
- 1-second bar ingestion rate
- tradable equity
- order approvals vs rejections

### Loki / Promtail

Logs from the trading stack are shipped into Loki via Promtail for centralized operational visibility.

---

## 20. Current Reality: Implemented vs Planned

### Clearly implemented

- Angel One historical sync
- Angel One live WebSocket tick ingestion
- Kafka tick and bar pipeline
- live enrichment into PostgreSQL
- model inference service
- signal service with regime and strategy flow
- gateway aggregation
- paper account, orders, fills, positions, account summary, and daily P&L
- stop-loss / take-profit auto-close monitor
- Prometheus and Grafana monitoring stack

### Present but incomplete

- institutional Kafka execution path after risk sizing

### Important architectural distinction

If someone asks, "How are orders placed right now?", the precise answer is:

- **manual and API-triggered paper orders are placed directly through the paper-trading service**
- **auto-generated institutional-style orders can be emitted to Kafka, but the repo does not yet contain the final execution consumer that completes that path**

---

## 21. End-to-End Flow Summary

```text
1. Angel One provides historical candles and live ticks
2. Historical gaps are backfilled into PostgreSQL through sync_data.py
3. Live ticks go to Kafka topic: ticks
4. ticks are aggregated into bars.1s
5. bars.1s are aggregated into bars.1m
6. bars.1m are enriched into ohlcv_enriched
7. Signal consumer reads bars.1m and fetches latest enriched features
8. signal-service classifies regime and runs strategies
9. model-service predicts probability, expected return, and expected drawdown
10. signal-service filters weak setups
11. target calculator produces entry, SL, L1, L2, L3
12. trade alerts are stored and exposed through the gateway/frontend
13. user may place direct paper orders through the paper OMS
14. paper OMS validates risk, simulates fills, updates positions, and adjusts cash
15. account endpoints compute realized P&L, unrealized P&L, and total equity
16. background monitor auto-closes positions on SL/TP
17. Prometheus, Grafana, and Loki monitor the whole system
```

---

## 22. One-Line System Description

This is a live intraday trading intelligence and paper-execution platform that extracts market data from Angel One, converts it into enriched features, predicts trade quality with an ML ensemble, generates filtered strategy signals, and tracks paper positions, cash, and P&L through a monitored microservice architecture.
