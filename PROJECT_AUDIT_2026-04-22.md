# Project Audit - April 22, 2026

## Executive Verdict

This project is **not ready for real-money trading**.

Current state is closer to a partially integrated research and paper-trading platform than a production trading system. There is useful work here: model artifacts exist, strategy code exists, live market-data ingestion exists, Kafka exists, Grafana exists, and a frontend exists. But the repo has clear drift between:

- documented architecture
- intended institutional architecture
- actual runtime path

The biggest issue is not that nothing works. The issue is that **some parts work, some parts are placeholders, and some critical live paths are not connected end to end**. That is the dangerous state for a money system.

---

## Final Recommendation

Do **not** deploy real capital on this stack in current form.

Acceptable next step:

- continue research
- continue paper trading
- harden the live pipeline
- remove fake/synthetic operator data
- unify the architecture
- add end-to-end verification

Only after that should real-money consideration begin.

---

## What I Audited

I reviewed:

- root compose and infra compose
- gateway
- signal-service
- model-service
- paper-trading-service
- AI, news, fundamentals, institutional, sentiment services
- Kafka/WebSocket ingestion and compute scripts
- frontend data flow
- observability configs
- feature engineering path

I also ran a syntax compilation pass over the main Python code.

What I did **not** verify:

- live broker connectivity
- actual market-session runtime behavior
- live container orchestration
- DB schema consistency against a running database
- model quality on unseen live sessions

This is therefore a **code and architecture audit**, not a production certification.

---

## Actual Architecture vs Claimed Architecture

### Claimed Architecture

The docs describe an institutional microservice stack:

`WebSocket -> Kafka -> bars -> signal engine -> model -> AI -> execution -> monitoring -> dashboard`

That is directionally reasonable.

### Actual Working Path Today

The most reliable path in the codebase today is:

`Frontend -> Gateway -> Signal Service / News / Fundamentals / Institutional / Sentiment / AI / Paper Trading`

with the dashboard and many APIs depending primarily on data already stored in PostgreSQL.

### Intended Live Kafka Path

The repo also contains an intended live path:

`Angel One WebSocket -> Kafka ticks -> 1s bars -> 1m bars -> Signal Consumer -> /process -> trade alerts -> Kafka orders -> Risk Manager`

But that path is **not fully wired into the main runtime stack**.

---

## How Kafka Is Used

Kafka is present and partially integrated.

### Kafka Entry Point

Market ticks are ingested from Angel One WebSocket and published into Kafka by:

- [scripts/ingestion/angel_one_ws.py](/home/sumanth/Desktop/trading-system/scripts/ingestion/angel_one_ws.py:63)

This script:

- logs in to Angel One
- subscribes to symbols over SmartWebSocketV2
- receives ticks
- pushes them to Kafka topic `ticks`

### Kafka Bar Pipeline

Ticks are transformed in two stages:

- [scripts/compute/bar_builder_1s.py](/home/sumanth/Desktop/trading-system/scripts/compute/bar_builder_1s.py:1)
- [scripts/compute/bar_aggregator_1m.py](/home/sumanth/Desktop/trading-system/scripts/compute/bar_aggregator_1m.py:1)

Flow:

- `ticks` -> `bars.1s`
- `bars.1s` -> `bars.1m`

These scripts also persist bars to Postgres.

### Kafka Order Publishing

The signal service can publish orders to Kafka using:

- [services/signal-service/app/services/order_client.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/order_client.py:41)

This publishes `NEW` orders to Kafka topic `orders`.

### Intended Kafka Risk Stage

There is a separate risk manager:

- [services/execution_service/app/services/risk_manager.py](/home/sumanth/Desktop/trading-system/services/execution_service/app/services/risk_manager.py:77)

It is intended to:

- consume `orders`
- size/reject
- publish approved orders to `orders.sized`

### Main Problem With Kafka Integration

The main compose file does **not** start the components that complete the live Kafka decision pipeline:

- no `bar_consumer.py` process
- no `risk_manager.py` process
- no actual execution service consuming approved orders

See:

- [docker-compose.yml](/home/sumanth/Desktop/trading-system/docker-compose.yml:105)

Conclusion:

- Kafka is present
- Kafka is not useless
- Kafka is **not fully connected to a running end-to-end trading path**

---

## When WebSockets Are Called

WebSockets are used **only for broker market-data ingestion**.

### Present Usage

Current WebSocket usage:

- Angel One SmartWebSocketV2 in [scripts/ingestion/angel_one_ws.py](/home/sumanth/Desktop/trading-system/scripts/ingestion/angel_one_ws.py:24)

This is the only meaningful WebSocket use I found in the project code.

### Not Used in Frontend

The frontend does **not** consume a backend WebSocket stream.

The UI refreshes by polling REST endpoints every 5 seconds:

- [frontend/src/App.tsx](/home/sumanth/Desktop/trading-system/frontend/src/App.tsx:102)

So the UI is **not truly real time** even if Kafka and WebSocket ingestion are active.

Conclusion:

- WebSockets are called at ingestion
- WebSockets are not used for trader-facing updates

---

## When Grafana Is Called

Grafana is configured as observability infrastructure, not as a core application service.

### Infra Stack

Grafana, Prometheus, Loki, and Promtail are started from:

- [infra/docker-compose.yml](/home/sumanth/Desktop/trading-system/infra/docker-compose.yml:49)

This is separate from the main app compose.

### Prometheus Targets

Prometheus scrapes metrics from ports defined in:

- [infra/prometheus/prometheus.yml](/home/sumanth/Desktop/trading-system/infra/prometheus/prometheus.yml:1)

### Dashboard

Grafana dashboard is defined in:

- [infra/grafana/dashboards/institutional_overview.json](/home/sumanth/Desktop/trading-system/infra/grafana/dashboards/institutional_overview.json:1)

### Main Problem With Grafana Integration

The Grafana dashboard expects risk-manager metrics like:

- `risk_manager_tradable_equity_inr`
- `risk_orders_approved_total`
- `risk_orders_rejected_total`

But the risk manager is not launched in the main stack.

Also Prometheus labels port `7003` as `ai_service`, but `7003` is model-service:

- [infra/prometheus/prometheus.yml](/home/sumanth/Desktop/trading-system/infra/prometheus/prometheus.yml:20)

Conclusion:

- Grafana is configured
- some metrics are real
- some dashboard assumptions depend on services not actually started
- observability is partial, not trustworthy enough for capital protection

---

## How The Core Backend Actually Works

### Gateway

Gateway is a thin HTTP proxy:

- [gateway/main.py](/home/sumanth/Desktop/trading-system/gateway/main.py:42)

It does not contain core trading logic. It forwards requests to backend services and serves the frontend build.

### Signal Service

This is the real core of the system:

- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:106)

The `POST /process` flow is:

1. classify market regime
2. run allowed strategies
3. call model service over HTTP
4. store raw strategy signal
5. apply signal filter
6. calculate targets
7. store trade alert
8. optionally ask AI to validate
9. optionally publish order to Kafka

This is the most important real trading logic in the repo.

### Model Service

Model service loads artifacts and returns:

- probability
- expected return
- expected drawdown
- confidence
- anomaly flag

See:

- [services/model-service/app/main.py](/home/sumanth/Desktop/trading-system/services/model-service/app/main.py:1)
- [services/model-service/app/services/ensemble.py](/home/sumanth/Desktop/trading-system/services/model-service/app/services/ensemble.py:1)

This service is real, but the model-serving path is only as good as the features sent into it.

### Paper Trading Service

This is a local simulated OMS and position tracker:

- [services/paper-trading-service/app/main.py](/home/sumanth/Desktop/trading-system/services/paper-trading-service/app/main.py:1)

It supports:

- create order
- list orders
- list fills
- close positions
- account summary

But it is not equivalent to a real broker execution layer.

---

## Current Strengths

These are the parts that are useful and worth preserving.

### 1. There Is a Real Service Structure

This is not a toy single-file script. It has separation across:

- signal generation
- model inference
- news/fundamental/institutional context
- paper trading
- gateway
- frontend

### 2. There Is a Real Streaming Foundation

You do have:

- broker WebSocket ingestion
- Kafka
- 1-second and 1-minute aggregation
- Prometheus metrics in ingestion/compute stages

That is valuable groundwork.

### 3. Signal Persistence Exists

You persist:

- raw strategy signals
- filtered trade alerts

That is good for auditability and later review.

### 4. Paper Trading Logic Exists

There is at least a first version of:

- order lifecycle
- fills
- positions
- PnL
- risk checks

That gives you a sandbox to harden operator flows before real money.

### 5. The Frontend Is Better Than a Demo Stub

The frontend is actually connected to backend APIs and can display:

- symbols
- history
- insights
- signals
- paper portfolio
- AI report

It is not complete, but it is useful as an operator console.

---

## Critical Gaps and Risks

## 1. Credentials Are Exposed In Repo

File:

- [/.env](/home/sumanth/Desktop/trading-system/.env:22)

The repository contains live broker credentials in plain text:

- `ANGEL_CLIENT_ID`
- `ANGEL_PIN`
- `ANGEL_API_KEY`
- `ANGEL_TOTP_SECRET`

This is unacceptable for a real-money system.

### Why This Is Serious

- anyone with repo access can use them
- secrets may already be copied into shell history, logs, backups, editor caches
- TOTP secret exposure is especially severe

### Immediate Action

Do this first:

1. rotate all Angel One credentials immediately
2. remove secrets from repo
3. move secrets to secret manager or ignored local env file
4. audit whether these credentials were reused anywhere else

---

## 2. Auto Paper Trading Is Enabled In Checked-In Env

File:

- [/.env](/home/sumanth/Desktop/trading-system/.env:28)

`AUTO_PAPER_TRADING_ENABLED=true`

This means signal service will automatically publish orders to Kafka when signals pass and AI approves:

- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:204)

For a system with incomplete Kafka execution wiring, this is unsafe even for paper stability.

---

## 3. Main Live Kafka Path Is Incomplete

The intended bar consumer exists:

- [services/signal-service/app/services/bar_consumer.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/bar_consumer.py:24)

But it is not part of main compose.

This consumer itself also admits it is incomplete:

- it sends fake minimal features
- `minutes_from_open` is hardcoded to `0`
- it says feature logic is still to be added

See:

- [bar_consumer.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/bar_consumer.py:42)

That means the true streaming signal engine is not production-ready.

### Impact

Even if:

- WebSocket is connected
- Kafka is alive
- bars are being built

you still do not have a trustworthy live decision engine consuming those bars in the main stack.

---

## 4. Execution/Risk Pipeline Exists But Is Not Integrated

There is a separate institutional risk manager:

- [services/execution_service/app/services/risk_manager.py](/home/sumanth/Desktop/trading-system/services/execution_service/app/services/risk_manager.py:54)

But:

- it is not in main compose
- no downstream execution consumer is wired in the main stack
- dashboard expects its metrics anyway

This creates a false impression of maturity.

### Additional Mismatch

Risk manager expects stop fields as:

- `entry_px`
- `stop_px`

but Kafka order payload from signal service sends:

- `stop_loss`
- `target_l1`
- `target_l2`
- `target_l3`

See:

- [order_client.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/order_client.py:62)
- [risk_manager.py](/home/sumanth/Desktop/trading-system/services/execution_service/app/services/risk_manager.py:113)

So even if risk manager were started, it would not size from the intended stop-loss fields without fixes.

---

## 5. Benchmark Display Is Not Real

File:

- [services/signal-service/app/services/market_data.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/market_data.py:103)

The app presents `NIFTY50`, but it is actually:

- RELIANCE as proxy symbol
- hardcoded breadth `30 advancers / 20 decliners`

This is a major operator-risk issue.

### Why It Matters

A trader looking at:

- benchmark move
- breadth
- regime context

may believe they are seeing market-level information, but they are actually seeing a single-stock proxy plus invented breadth.

That is unacceptable in any capital allocation workflow.

---

## 6. Synthetic Values Are Being Served To The Frontend

File:

- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:344)

`/insights` returns:

- confidence hardcoded as `0.75`
- `source_status: "synthetic"`

This means the UI can look precise even when the value is not real.

For a money system, synthetic values must be clearly isolated or removed.

---

## 7. Feature Engineering Still Contains Placeholders

File:

- [shared/feature_engineer.py](/home/sumanth/Desktop/trading-system/shared/feature_engineer.py:150)

Placeholder values include:

- `sector = 'Unknown'`
- `sector_return = 0.0`
- `sector_strength = 0.0`
- `return_rank = 0.0`
- `volume_rank = 0.0`
- `return_percentile = 0.0`
- `volume_percentile = 0.0`

### Direct Consequence

Relative Strength strategy depends on percentile ranks:

- [services/signal-service/app/strategies/relative_strength.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/strategies/relative_strength.py:37)

Because those ranks are hardcoded to zero, this strategy effectively does not work as described.

So the claimed “7-strategy system” is overstated.

---

## 8. Strategy Input Mismatches Exist

### Volatility Squeeze

Strategy reads:

- `Bollinger_%B`

See:

- [volatility_squeeze.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/strategies/volatility_squeeze.py:44)

But feature engineering creates:

- `bollinger_b`

See:

- [shared/feature_engineer.py](/home/sumanth/Desktop/trading-system/shared/feature_engineer.py:158)

Because the base strategy only tries exact key and lowercase key:

- [base_strategy.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/core/base_strategy.py:21)

`Bollinger_%B` does not map to `bollinger_b`.

Result:

- this strategy likely never gets valid input
- strategy diagnostics may still display plausible text

That is dangerous.

---

## 9. AI Validation Is Over-Coupled And Under-Grounded

Signal service enables AI validation by default:

- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:73)

Then it passes weak context:

- no real news
- no real institutional data
- placeholder technical summary

See:

- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:189)

If AI rejects or is unavailable, signal is suppressed:

- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:198)

### Why This Is a Problem

AI should not be a silent production gatekeeper unless:

- context is reliable
- behavior is benchmarked
- failure mode is explicitly designed

Right now it is too easy for AI availability or weak prompting to block signals unpredictably.

---

## 10. Paper Trading API Has Implementation Defects

File:

- [services/paper-trading-service/app/main.py](/home/sumanth/Desktop/trading-system/services/paper-trading-service/app/main.py:103)

`GET /positions` updates in-memory position fields but does **not return a response**.

That is a real bug.

### Additional Issue

Risk validation requires `paper_accounts.id = 1` to exist:

- [risk_service.py](/home/sumanth/Desktop/trading-system/services/paper-trading-service/app/services/risk_service.py:36)

But service startup only creates tables, not the account seed row. The seed row is created separately by:

- [scripts/init_paper_db.py](/home/sumanth/Desktop/trading-system/scripts/init_paper_db.py:99)

So paper trading depends on manual DB initialization outside service startup.

---

## 11. Sentiment Service Has Container Networking Problem

File:

- [services/sentiment-service/app/main.py](/home/sumanth/Desktop/trading-system/services/sentiment-service/app/main.py:18)

It hardcodes:

- `GATEWAY_URL = "http://127.0.0.1:8000"`

Inside Docker, `127.0.0.1` points to the sentiment container itself, not the gateway container.

So this service will fail in normal containerized deployment unless run on host or changed to service DNS.

---

## 12. Frontend Is REST-Polling, Not Streaming

The dashboard refreshes every 5 seconds:

- [frontend/src/App.tsx](/home/sumanth/Desktop/trading-system/frontend/src/App.tsx:102)

The stock page loads data on mount only:

- [frontend/src/pages/StockPage.tsx](/home/sumanth/Desktop/trading-system/frontend/src/pages/StockPage.tsx:29)

There is no frontend WebSocket subscription for:

- ticks
- new alerts
- fills
- order status transitions

So the operator interface is not real-time.

---

## 13. Observability Is Only Partially Trustworthy

Prometheus is configured to scrape:

- ingestor metrics
- bar builders
- risk manager
- signal service
- model service mislabeled as AI

See:

- [infra/prometheus/prometheus.yml](/home/sumanth/Desktop/trading-system/infra/prometheus/prometheus.yml:5)

Grafana dashboard depends heavily on metrics from risk manager:

- [institutional_overview.json](/home/sumanth/Desktop/trading-system/infra/grafana/dashboards/institutional_overview.json:49)

But risk manager is not part of the main app stack.

This means observability can look healthy while the actual decision path is incomplete.

---

## What Is Actually Safe To Trust Right Now

You can reasonably use this repo for:

- historical data sync and feature engineering experiments
- model inference experiments
- strategy logic review
- paper trading experiments after fixing service bugs
- UI prototyping
- observability prototyping

You should **not** trust it yet for:

- live decisioning with capital
- benchmark-aware macro decisions
- execution automation
- institutional-grade risk management
- production incident response

---

## Real-Money Blockers

These are the blockers that must be resolved before even small capital.

### Blocker 1

Secrets management and credential rotation.

### Blocker 2

Single authoritative production architecture.

Right now there are multiple partially overlapping systems:

- DB-driven UI path
- Kafka intended path
- paper OMS path
- separate execution_service path

You need one coherent live path.

### Blocker 3

True end-to-end live signal pipeline:

- tick
- bar
- feature enrichment
- regime
- strategy
- model
- filter
- alert
- order
- risk
- execution
- reconciliation

### Blocker 4

Remove all fake operator values:

- RELIANCE proxy benchmark
- hardcoded breadth
- synthetic confidence
- placeholder ranks

### Blocker 5

Fix strategy input mismatches and verify each strategy on real data.

### Blocker 6

Make AI advisory, not silent critical gatekeeper, until proven.

### Blocker 7

Add production safety controls:

- kill switch
- startup dependency checks
- broker reconciliation
- daily reset automation
- position and exposure caps
- stuck-order detection
- stale-data detection
- market-hours guardrails

### Blocker 8

Add integration and replay tests for live path.

---

## Recommended Immediate Action Plan

## Phase 1 - Emergency Cleanup

Do immediately:

1. rotate Angel One credentials
2. remove secrets from tracked files
3. set `AUTO_PAPER_TRADING_ENABLED=false`
4. fix paper `/positions` endpoint
5. fix sentiment-service gateway URL for containers

## Phase 2 - Remove Misleading Operator Data

Do next:

1. remove RELIANCE-as-NIFTY proxy
2. remove hardcoded breadth
3. remove synthetic confidence from UI output
4. clearly mark any placeholder value as unavailable instead of fake precision

## Phase 3 - Unify The Live Architecture

Pick one live architecture and finish it:

1. WebSocket ingestion
2. Kafka bars
3. enriched feature generation from streaming bars
4. signal consumer process in compose
5. risk manager in compose
6. downstream execution or paper execution consumer

## Phase 4 - Strategy And Feature Integrity

1. fix feature key mismatches
2. implement true cross-symbol ranking for relative strength
3. verify every strategy with replayed intraday data
4. publish per-strategy firing statistics

## Phase 5 - Production Safety

1. automated daily reset
2. stale-data watchdog
3. circuit breaker / kill switch
4. order reconciliation
5. position reconciliation
6. alerting for service degradation

## Phase 6 - Real-Money Readiness Gate

Before any real money:

1. run stable paper trading for multiple weeks
2. compare expected vs realized execution
3. validate operator workflows
4. review worst-case failure paths
5. confirm no synthetic data remains in trader-critical views

---

## Honest Summary

This project has strong ambition and some solid building blocks, but it is not yet an honest “institutional-grade trading system.”

Right now it is:

- a meaningful prototype
- a decent research platform
- a partly wired live-data system
- a not-yet-safe execution environment

The most dangerous issue is not one single bug. It is the combination of:

- real-looking UI
- partially real pipelines
- placeholder analytics
- disconnected live stages
- exposed credentials

That combination can create false confidence. False confidence is exactly what loses money in trading systems.

---

## Suggested Next Deliverables

I recommend creating these next:

1. `REMEDIATION_PLAN_2026-04-22.md`
2. `LIVE_ARCHITECTURE_DECISION.md`
3. `PRODUCTION_READINESS_CHECKLIST.md`
4. `SECRETS_AND_ENV_GUIDE.md`
5. `INTEGRATION_TEST_PLAN.md`

If needed, the next step can be a concrete remediation document with:

- priority
- effort
- risk
- exact files to change
- recommended sequence over 1 to 3 weeks
