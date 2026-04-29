# Comparison Diff: Your Trading System vs Friend's Trading Platform

Date: 2026-04-11

Compared repos:

- Yours: `/home/sumanth/Desktop/trading-system`
- Friend's: `https://github.com/SreemukhMantripragada/trading-platform/tree/main`
  Compared via read-only clone at `/tmp/friend-trading-platform`

Scope:

- architecture
- ingestion/data pipeline
- feature/model/training
- strategy layer
- risk/execution
- frontend/UI
- infra/ops/observability

This is a comparison file only. Your application code was not changed.

## Executive Difference

Your repo and your friend's repo are not the same type of system.

- Your repo is an ML-first intraday advisory platform with:
  - feature engineering
  - ensemble scoring
  - strategy filtering
  - React dashboard
  - AI/Gemma analysis

- Your friend's repo is an execution-first event-driven trading platform with:
  - Kafka-centric streaming
  - ingestion and bar pipelines
  - risk engines
  - OMS/execution stack
  - Docker/Prometheus/Grafana
  - orchestration and operational tooling

Short version:

- You are ahead in ML scoring, UI, and AI-assisted decision presentation.
- Your friend is far ahead in infra, execution maturity, risk controls, and operations.

## Top-Level Structural Diff

### Your repo

Main shape:

- `services/` microservices
- `frontend/` React dashboard
- `gateway/`
- `scripts/` for data/training
- `shared/feature_engineer.py`

Main runtime idea:

- synchronous HTTP-style service mesh
- DB-backed reads
- ML scoring service
- signal filtering and display

### Friend repo

Main shape:

- `ingestion/`
- `compute/`
- `strategy/`
- `risk/`
- `execution/`
- `monitoring/`
- `orchestrator/`
- `infra/`
- `analytics/`
- `backtest/`
- `ui/`

Main runtime idea:

- event-driven Kafka mesh
- staged market-data processing
- explicit risk and execution layers
- operational tooling around the live loop

## Architecture Diff

### Your architecture

Strengths:

- clear service separation for model, signal, news, sentiment, fundamentals, institutional, AI, frontend
- simpler to reason about at prototype/advisory stage
- easier for dashboard-centric iteration

Weaknesses:

- architecture claims exceed implementation in some places
- no real event bus
- no proper execution layer
- no proper operational control plane

Key files:

- [README.md](/home/sumanth/Desktop/trading-system/README.md)
- [gateway/main.py](/home/sumanth/Desktop/trading-system/gateway/main.py:1)
- [services/signal-service/app/main.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/main.py:1)

### Friend architecture

Strengths:

- explicitly event-driven and replayable
- ingestion -> compute -> strategy -> risk -> OMS -> gateway is better defined
- docs reflect architecture choices directly
- process supervision and infra are already first-class

Weaknesses:

- less product polish on user-facing dashboarding
- less visible emphasis on ML/AI decision intelligence
- more operational complexity

Key files:

- `/tmp/friend-trading-platform/README.md`
- `/tmp/friend-trading-platform/docs/architecture_tech_choices.md`
- `/tmp/friend-trading-platform/infra/docker-compose.yml`

## Data Ingestion Diff

### Your repo

What exists:

- Angel One client helper
- sync scripts
- parquet and DB ingestion scripts
- feature engineering pipeline

Key files:

- [scripts/sync_data.py](/home/sumanth/Desktop/trading-system/scripts/sync_data.py:1)
- [services/data_service/app/services/angel_one_client.py](/home/sumanth/Desktop/trading-system/services/data_service/app/services/angel_one_client.py:1)
- [shared/feature_engineer.py](/home/sumanth/Desktop/trading-system/shared/feature_engineer.py:1)

Gaps:

- no real runtime data-service entrypoint
- no feature-service runtime
- no streaming ingestion fabric
- not production-grade for live market event handling

### Friend repo

What exists:

- websocket ingestion
- historical merge tools
- DLQ consumer
- token-building scripts
- 1s and 1m bar builders
- multi-timeframe aggregation

Key files:

- `/tmp/friend-trading-platform/ingestion/zerodha_ws.py`
- `/tmp/friend-trading-platform/compute/bar_builder_1s.py`
- `/tmp/friend-trading-platform/compute/bar_aggregator_1m.py`
- `/tmp/friend-trading-platform/compute/bar_aggregator_1m_to_multi.py`

Verdict:

- Friend repo is much stronger in live ingestion and streaming data engineering.
- Your repo is stronger in post-ingestion feature enrichment for ML-oriented signals.

## Feature Engineering / Modeling Diff

### Your repo

Major strength area.

What exists:

- 70+ feature engineering path
- ensemble model service
- anomaly detector
- classification + MFE + MAE stack
- training and walk-forward scripts
- AI/Gemma layer on top

Key files:

- [shared/feature_engineer.py](/home/sumanth/Desktop/trading-system/shared/feature_engineer.py:11)
- [scripts/training/train_ensemble.py](/home/sumanth/Desktop/trading-system/scripts/training/train_ensemble.py:1)
- [services/model-service/app/services/ensemble.py](/home/sumanth/Desktop/trading-system/services/model-service/app/services/ensemble.py:1)
- [services/ai-service/app/main.py](/home/sumanth/Desktop/trading-system/services/ai-service/app/main.py:1)

Weaknesses:

- current training pipeline reproducibility is weak
- target columns appear missing from the main parquet store
- some live/display fields are still placeholder quality

### Friend repo

What exists:

- model registry abstraction
- strategy and ranking engine
- backtest/scoring promotion system

Key files:

- `/tmp/friend-trading-platform/ml/model_registry.py`
- `/tmp/friend-trading-platform/backtest/scorer.py`
- `/tmp/friend-trading-platform/strategy/ensemble_engine.py`

Weakness:

- not visibly as advanced as your repo in integrated ML inference + feature-service style advisory scoring
- AI-assisted layer is absent

Verdict:

- You are ahead in ML-advisory stack design.
- Friend repo is ahead in research-to-live operational discipline.

## Strategy Diff

### Your repo

What exists:

- 6 concrete strategies + regime classifier
- signal filtering
- target calculator
- live dashboard consumption

Key files:

- [services/signal-service/app/strategies/orb.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/strategies/orb.py:1)
- [services/signal-service/app/strategies/vwap_reversion.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/strategies/vwap_reversion.py:1)
- [services/signal-service/app/strategies/momentum.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/strategies/momentum.py:1)
- [services/signal-service/app/services/signal_filter.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/signal_filter.py:1)

Weakness:

- strategy-to-label consistency is not yet rigorous enough
- live and backtest target generation have inconsistencies

### Friend repo

What exists:

- strategy registry
- modular runners
- ensemble strategy engine
- YAML-based promotion and selection

Key files:

- `/tmp/friend-trading-platform/strategy/runner_unified.py`
- `/tmp/friend-trading-platform/strategy/runner_modular.py`
- `/tmp/friend-trading-platform/strategy/ensemble_engine.py`
- `/tmp/friend-trading-platform/strategy/registry.yaml`

Strength:

- more mature runtime strategy orchestration
- better config-driven deployment model

Verdict:

- Your repo has stronger productized signal presentation.
- Friend repo has stronger runtime strategy operations.

## Risk Diff

### Your repo

Current state:

- risk is mostly implicit through signal thresholds and target calculation
- no true portfolio risk engine
- no order budget guard
- no kill switch

Key files:

- [services/signal-service/app/services/signal_filter.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/signal_filter.py:4)
- [services/signal-service/app/services/target_calculator.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/services/target_calculator.py:4)

### Friend repo

Current state:

- explicit risk manager
- position sizing
- spend tracking
- risk budget config
- kill switch

Key files:

- `/tmp/friend-trading-platform/risk/manager_v2.py`
- `/tmp/friend-trading-platform/risk/position_sizer.py`
- `/tmp/friend-trading-platform/risk/order_budget_guard.py`
- `/tmp/friend-trading-platform/libs/killswitch.py`

Verdict:

- Friend repo is substantially ahead in real trading safety controls.
- This is the single largest maturity gap between the two repos.

## Execution Diff

### Your repo

Current state:

- advisory system, not broker-execution capable
- no OMS
- no order state machine
- no broker reconciliation

Your own docs also say this is not auto-trading yet.

### Friend repo

Current state:

- OMS
- paper gateway
- Zerodha gateway
- matcher
- fills path
- exit engine
- accounting and reconciliation

Key files:

- `/tmp/friend-trading-platform/execution/oms.py`
- `/tmp/friend-trading-platform/execution/paper_gateway.py`
- `/tmp/friend-trading-platform/execution/zerodha_gateway.py`
- `/tmp/friend-trading-platform/execution/exit_engine.py`

Verdict:

- Friend repo is far ahead in actual tradable system architecture.

## UI / Product Diff

### Your repo

This is a strong area.

What exists:

- React frontend
- symbol views
- charting
- signals gallery
- stock page
- news/fundamentals/sentiment/institutional/AI integration

Key files:

- [frontend/src/App.tsx](/home/sumanth/Desktop/trading-system/frontend/src/App.tsx:1)
- [frontend/src/pages/StockPage.tsx](/home/sumanth/Desktop/trading-system/frontend/src/pages/StockPage.tsx:1)
- [frontend/src/api/market.ts](/home/sumanth/Desktop/trading-system/frontend/src/api/market.ts:1)

Weakness:

- some displayed data is still proxy/placeholder-derived

### Friend repo

What exists:

- Streamlit-style operational UIs
- monitoring dashboards
- backtest and pairs watch views

Key files:

- `/tmp/friend-trading-platform/ui/backtest_app.py`
- `/tmp/friend-trading-platform/ui/pairs_watch_and_trade_dashboard.py`

Verdict:

- You are ahead in user-facing product UI.
- Friend repo is ahead in operator-facing monitoring UI.

## Infra / DevOps Diff

### Your repo

Current state:

- no Docker stack committed
- no Kafka
- no Nginx layer
- no Prometheus/Grafana
- no Kubernetes manifests
- limited process orchestration

### Friend repo

Current state:

- Docker stack
- Kafka + Zookeeper
- Kafka UI
- topic init scripts
- Postgres service
- Prometheus
- Grafana
- process supervisor
- GitHub workflows

Key files:

- `/tmp/friend-trading-platform/infra/docker-compose.yml`
- `/tmp/friend-trading-platform/infra/scripts/create-topics.sh`
- `/tmp/friend-trading-platform/.github/workflows/*.yml`

Verdict:

- Friend repo is much more mature operationally.
- Your current tasks file is correct to add Docker, Kafka, Nginx, and Kubernetes as major next items.

## Observability Diff

### Your repo

Current state:

- log files exist
- no real metrics/exporter stack visible
- no alerting layer

### Friend repo

Current state:

- Prometheus exporters
- Grafana dashboards
- doctor/recon scripts
- health-oriented monitoring tools

Verdict:

- Friend repo is significantly ahead in observability.

## Documentation Diff

### Your repo

Strength:

- clear product vision
- strong system-story documentation

Weakness:

- docs currently overstate readiness in a few places

### Friend repo

Strength:

- deeper engineering docs
- architecture decision explanations
- repo catalog and runbooks

Verdict:

- Friend repo has stronger engineering-operational documentation.
- Your repo has stronger product/business framing.

## Side-By-Side Scorecard

Scale:

- `Strong`
- `Medium`
- `Weak`

| Area | Your Repo | Friend Repo | Who Is Ahead |
|---|---|---|---|
| Product UI | Strong | Medium | You |
| ML inference | Strong | Medium | You |
| AI/Gemma integration | Strong | Weak | You |
| Feature engineering | Strong | Medium | You |
| Live ingestion architecture | Medium | Strong | Friend |
| Streaming/event bus | Weak | Strong | Friend |
| Risk engine | Weak | Strong | Friend |
| OMS/execution | Weak | Strong | Friend |
| Infra/containers | Weak | Strong | Friend |
| Observability | Weak | Strong | Friend |
| Process supervision | Weak | Strong | Friend |
| Strategy config/runtime ops | Medium | Strong | Friend |
| Research/backtest discipline | Medium | Strong | Friend |

## What You Have That Your Friend Does Not

- dedicated ML ensemble microservice
- explicit anomaly detector in model inference
- AI/Gemma institutional-analysis layer
- richer end-user stock page and dashboard UX
- integrated sentiment/news/fundamentals/institutional UI story
- advisory-first product framing

## What Your Friend Has That You Do Not

- Kafka-first runtime
- execution stack and OMS
- risk engine and budget controls
- stronger runtime orchestration
- Dockerized full stack
- observability platform
- workflow automation
- more production-like live trading backbone

## Most Important Practical Conclusion

If the goal is:

- `advisory + ML dashboard`: your repo is ahead
- `real trading platform / execution infrastructure`: your friend’s repo is ahead

Right now your repo is better described as:

- intelligent advisory/trade-selection platform

Your friend’s repo is better described as:

- operational trading infrastructure platform

## Recommended Interpretation For Your Next Steps

Do not try to copy the entire friend repo blindly. The better move is to selectively absorb the missing maturity layers.

## Best Borrowing Targets From Friend Repo

### Borrow soon

- Kafka/event-driven backbone
- risk manager concept
- OMS/order lifecycle discipline
- Docker full-stack startup
- process supervisor model
- Prometheus/Grafana observability

### Borrow later

- deeper execution adapters
- reconciliation/auto-heal workflows
- full paper/live switch discipline

### Keep your own strengths

- ML ensemble service
- feature engineering direction
- AI/Gemma analysis layer
- React UI and dashboard product experience

## Recommended Combined Architecture

Best merged direction:

1. Keep your ML + advisory + UI stack.
2. Add Kafka between ingestion, features, signals, and audit events.
3. Add a real risk service before any execution path.
4. Add OMS and paper execution first.
5. Add Docker/Nginx/Prometheus/Grafana.
6. Add Kubernetes only after the Dockerized stack is stable.

## Final Verdict

Your repo is better at:

- intelligence
- scoring
- explainability
- trader-facing experience

Your friend’s repo is better at:

- system engineering
- runtime robustness
- execution readiness
- infra maturity

So the real diff is:

- your project has better brains
- your friend’s project has better backbone

That is the cleanest comparison.
