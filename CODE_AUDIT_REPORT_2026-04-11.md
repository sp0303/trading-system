# Trading System Full Audit Report

Date: 2026-04-11
Scope: data pipeline, feature engineering, model/training, signal generation, backtesting, API/gateway, frontend, AI/Gemma, and operational readiness.

## Executive Summary

This codebase is not an empty skeleton. It has a working multi-service shape, a populated parquet feature store, trained model artifacts, a running frontend, and a signal-generation pipeline. The main risk is not syntax or packaging. The main risk is that several critical paths still use placeholders, proxies, or inconsistent feature/target assumptions, which means Monday testing can easily produce misleading results even if the services start successfully.

In short:

- The project is structurally built.
- The frontend builds and the Python files compile.
- The live/demo stack is only partially production-real.
- The largest problems are data/target integrity, target-calculation consistency, benchmark/UI placeholder logic, and gaps between the README claims and the actual implementation.

## What Is Actually Completed

### 1. Core service structure exists

- `gateway/main.py` proxies requests to backend services.
- `services/model-service/app/main.py` exposes `/predict` and loads serialized model artifacts.
- `services/signal-service/app/main.py` exposes `/process`, `/signals`, `/symbols`, `/history`, `/benchmark`, and `/insights`.
- `services/news-service/app/main.py`, `services/fundamental-service/app/main.py`, `services/institutional-service/app/main.py`, `services/sentiment-service/app/main.py`, and `services/ai-service/app/main.py` exist and are wired into the gateway.

### 2. Strategy engine is implemented

The following strategies exist in code and are wired into the signal service:

- ORB
- VWAP Reversion
- Momentum
- Relative Strength
- Volatility Squeeze
- Volume Reversal
- Regime classifier

### 3. Feature store exists and is substantial

- `data/mode_ready_data` contains 80 enriched parquet files.
- Sample inspection shows files are populated and have 71 columns.
- Feature engineering exists in `shared/feature_engineer.py`.

### 4. Model artifacts exist

`services/model-service/app/models` contains saved joblib artifacts for:

- probability models
- MFE models
- MAE models
- scaler
- label encoders
- anomaly detector
- meta models

### 5. Frontend is functional at build level

Verification run:

- `npm run build` succeeded
- `npm run lint` succeeded

### 6. Python syntax is clean

Verification run:

- `./trading-system/bin/python -m py_compile ...` succeeded for the main backend, scripts, and audit files.

## What Is Not Completed Or Not Truly Production-Ready

### 1. True live market benchmark is not implemented

`services/signal-service/app/services/market_data.py:89-116` returns NIFTY data using `RELIANCE` as a proxy and hardcoded breadth values.

Impact:

- Dashboard can look healthy while showing non-benchmark truth.
- Any test on market breadth or benchmark-relative logic is not trustworthy.

### 2. Symbol metadata is still placeholder-quality

`services/signal-service/app/services/market_data.py:33-40` returns:

- `label = symbol`
- `change_pct = 0.0`
- `sector = "Other"`

Impact:

- Watchlist and stock page are not using real daily change or sector metadata.
- Relative-strength UX is misleading.

### 3. Insights endpoint still contains placeholder confidence

`services/signal-service/app/main.py:234-240` hardcodes:

- `"confidence": 0.75`

Impact:

- Frontend strategy/model display is not fully based on real backend model output.

### 4. Institutional flow service is not reliable enough for production claims

`services/institutional-service/app/main.py:36-47` returns a successful response with fallback mock values when NSE access fails.

Impact:

- UI can silently display synthetic institutional data as if it were live.
- Operational outages become hard to detect.

### 5. AI/Gemma integration is basic orchestration, not a validated decision layer

`services/ai-service/app/main.py:17-72` sends a prompt to `gemma:2b` and returns raw markdown. There is:

- no output validation
- no timeout/retry policy
- no response schema enforcement
- no traceability or guardrails beyond prompt text

Impact:

- Good for demo reasoning, not reliable enough for live trading support decisions.

## Critical Mistakes And Risks, Priority-Wise

## P0 - Must fix before Monday live-like testing

### P0.1 Training data appears to be missing the target columns required by the trainer

Evidence:

- `scripts/training/train_ensemble.py` expects `target_prob`, `target_mfe`, `target_mae`.
- Sample parquet inspection showed these columns are absent in `data/mode_ready_data`.
- `scripts/training/export_db_to_parquet.py:37-40` even comments that targets may not exist, but does not generate them.

Impact:

- Model retraining is not reproducible from the current feature store.
- Any claim that the current export path is training-ready is weak.
- If retraining is required before Monday, it will likely fail or produce an empty dataset.

Recommended action:

- Confirm where the real target-labeled dataset is generated.
- Either persist targets into DB/parquet or make training use the correct labeled source explicitly.

### P0.2 Live signal target calculation is likely using the wrong ATR key and falling back to `0.01`

Evidence:

- Signal service uses `features.get("ATR_14") or 0.01` at `services/signal-service/app/main.py:123-127`.
- Backtest uses the same pattern at `services/signal-service/scripts/mass_backtest.py:174-177`.
- Feature engineering stores lowercase `atr_14` at `shared/feature_engineer.py:101-109`.
- Sample parquet inspection confirmed `atr_14` exists and `ATR_14` does not.

Impact:

- Stop loss and target levels can be materially wrong in live processing and backtesting.
- That directly corrupts risk/reward, pnl audit quality, and trader alerts.

Recommended action:

- Use the same case-insensitive helper logic here as the strategies do.
- Backtest and live service must share one target-input normalization path.

### P0.3 Target engineering script only labels ORB-style long breakouts, not the multi-strategy system described in the docs

Evidence:

- `scripts/calculate_targets.py:10-90` only computes ORB breakout targets.
- `scripts/calculate_targets.py:41` explicitly says “Long only for this version”.

Impact:

- The current labeling path does not match a 6-strategy/7-strategy multi-regime system.
- Ensemble training can become structurally mismatched from how signals are actually produced.

Recommended action:

- Decide whether the ML layer is strategy-agnostic or strategy-specific.
- Rebuild target generation to align with actual trade entry logic used by the signal engine.

### P0.4 Data/README claim mismatch creates false readiness

Evidence:

- README and guide say Data Service and Feature Service are part of the runtime architecture.
- Workspace contains only `services/data_service/app/services/angel_one_client.py`; there is no actual FastAPI data service entrypoint and no feature service implementation.

Impact:

- “Full stack ready” is overstated.
- Monday testing may start without a true live ingestion service boundary.

Recommended action:

- Rewrite the readiness document to match reality.
- If live ingestion is required Monday, define the actual launch path and ownership clearly.

## P1 - High priority, should be fixed immediately after P0

### P1.1 Signal filter threshold is inconsistent with the project progress document

Evidence:

- `services/signal-service/app/services/signal_filter.py:9` uses `mae_threshold=3.0`.
- `PROGRESS.md` says `mae_threshold` was fixed to `0.5`.

Impact:

- Risk gate may be much looser than intended.
- Backtest/live selection behavior may not match documented assumptions.

Recommended action:

- Decide the real threshold and keep code/docs aligned.
- Add test coverage for filter thresholds.

### P1.2 Model service hardcodes regime to `Trending`

Evidence:

- `services/model-service/app/main.py:42-55` sets `regime = "Trending"` as default.

Impact:

- Model output payload is semantically misleading.
- Downstream analytics or UI consumers may treat model output as regime-aware when it is not.

Recommended action:

- Remove regime from model service response, or explicitly mark it as external.
- Let signal service own regime entirely.

### P1.3 Feature engineering still contains placeholder market context and ranking fields

Evidence:

- `shared/feature_engineer.py:154-163` sets:
  - `sector = 'Unknown'`
  - `sector_return = 0.0`
  - `sector_strength = 0.0`
  - `return_rank = 0.0`
  - `volume_rank = 0.0`
  - `return_percentile = 0.0`
  - `volume_percentile = 0.0`

Impact:

- Relative Strength strategy is structurally weakened or invalid if sync-generated data is used.
- Sector-aware modeling is degraded.

Recommended action:

- Build a true cross-symbol ranking pass after enrichment.
- Maintain a symbol-to-sector mapping dataset.

### P1.4 Frontend still displays partly synthetic backend-derived data

Evidence:

- benchmark is proxy-based
- symbols use placeholder sector/change values
- insights confidence is hardcoded
- institutional service can silently fall back to mock success

Impact:

- The UI looks integrated, but the displayed truth is mixed-quality.

Recommended action:

- Add source-quality flags in API responses.
- Display stale/mock/proxy badges on the frontend.

## P2 - Medium priority, important for robustness and auditability

### P2.1 Signal service commits row-by-row in live processing

Evidence:

- `services/signal-service/app/main.py:120-121` commits each raw signal.
- `services/signal-service/app/main.py:145-146` commits each trade alert.

Impact:

- High DB overhead under load.
- Harder to preserve atomicity between raw signal and filtered alert creation.

Recommended action:

- Use one transaction per processed event.
- Roll back both raw and filtered writes together if needed.

### P2.2 Global strategy instances in live service can be fragile

Evidence:

- `services/signal-service/app/main.py:28-37` instantiates shared global strategy objects.

Impact:

- State management depends on strict day-reset discipline.
- Concurrency or multi-worker deployment can create divergent behavior.

Recommended action:

- Define explicit state ownership.
- If running multiple workers, move strategy state to external storage or partitioned in-memory orchestration.

### P2.3 Sentiment service depends on gateway instead of directly on news service

Evidence:

- `services/sentiment-service/app/main.py` fetches `http://127.0.0.1:8000/news`.

Impact:

- Unnecessary coupling.
- Makes service topology less clean and can complicate failure diagnosis.

Recommended action:

- Call news service directly or move sentiment into the news service.

### P2.4 Hardcoded absolute paths reduce portability

Evidence:

- `services/signal-service/scripts/mass_backtest.py:50`
- `services/signal-service/scripts/pnl_auditor.py` uses the same pattern

Impact:

- Environment migration is harder.
- CI or containerization will be brittle.

Recommended action:

- Move paths into env/config.

## P3 - Lower priority but should be cleaned up

### P3.1 Docs overstate completion

The README, guide, and progress files currently read as if all runtime components are production-grade. They are not.

### P3.2 Unused or weak abstractions exist

- Minimal `OHLCVEnriched` ORM in `services/signal-service/app/models/schema.py` does not represent the full feature table.
- Some imports and comments still describe systems that are not present as runtime services.

### P3.3 AI rendering is raw line splitting

`frontend/src/pages/StockPage.tsx:160-166` renders Gemma output by splitting lines into `<p>` tags instead of true markdown rendering.

## What I Would Trust For Monday Testing

### Safe to test

- Basic service startup
- Gateway routing
- Frontend navigation
- Signal retrieval and display plumbing
- Model artifact loading
- Strategy trigger logic at a code-path level

### Do not trust yet without fixes

- Benchmark truth
- Institutional-flow truth
- Strategy confidence truth on the stock page
- Stop/target accuracy
- Retraining reproducibility from current parquet store
- Any comparison of live-vs-backtest pnl

## Monday Test Plan

### Blockers to resolve before starting

1. Fix ATR key consistency in live and backtest target calculations.
2. Decide and enforce the real MAE threshold.
3. Confirm the authoritative target-labeled training dataset.
4. Mark benchmark/institutional/mock/proxy responses explicitly.
5. Update docs so the team tests the real system, not the imagined one.

### Monday smoke tests

1. Start model-service, signal-service, gateway, news, fundamentals, institutional, sentiment, ai, and frontend.
2. Hit `/health` on each service.
3. Verify `/symbols`, `/history`, `/signals`, `/insights`, `/benchmark`.
4. Inject one known feature payload into `/process` and verify DB writes.
5. Confirm stop loss and target levels use real `atr_14`.
6. Trigger one Gemma analysis and verify graceful failure if Ollama/model is unavailable.

### Monday validation tests

1. Compare one symbol’s alert targets against manual ATR math.
2. Compare benchmark payload against actual NIFTY data source, not RELIANCE proxy.
3. Verify relative-strength inputs are non-placeholder.
4. Audit at least 20 recent signals end-to-end from features to UI card.
5. Run backtest on a narrow date window and verify generated trade targets.

## Bottom-Line Status

### Overall status

- Architecture: partially complete
- Data pipeline: partially complete
- Feature engineering: substantial but still placeholder in important areas
- Model inference: implemented
- Model training reproducibility: not yet trustworthy
- Signal engine: implemented but has risk-calculation inconsistency
- Backtesting: implemented but inherits the same target-calculation issue
- Frontend: integrated, but some displayed data is still placeholder/proxy
- AI/Gemma: demo-capable, not decision-grade

### Go/No-Go for Monday

Recommendation: go ahead with Monday testing only as a controlled integration test, not as a production-readiness signoff.

The system is ready for:

- service integration testing
- UI verification
- API contract verification
- logic-path debugging

The system is not yet ready for:

- trustworthy performance evaluation
- trustworthy live advisory decisions
- retraining confidence
- benchmark-relative decision support
