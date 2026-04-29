# 🚀 Nifty 500 Elite Algorithmic Trading System

> [!IMPORTANT]
> **New to the project?** Please read the [**SYSTEM_GUIDE.md**](file:///home/sumanth/Desktop/trading-system/SYSTEM_GUIDE.md) for complete instructions on data syncing, training, and running the services.

---

## 🏆 MOTTO

> **"Systematic Edge. Institutional Grade. Trader in Control."**

The machine finds the edge. The trader makes the call. No guessing. No emotions. Only signals that pass strict statistical and risk filters are presented to the user.

---

## 🎯 AIM

Build a **production-grade intraday trading ADVISORY system** for Nifty 500 stocks that:

1. Identifies high-probability trade setups using **7 parallel quantitative strategies**
2. Uses a **10-model ML ensemble** to score every potential trade
3. **Alerts the trader** with complete trade details (entry, stop loss, 3 target levels)
4. Lets the trader decide — **BUY, SHORT SELL, or SKIP** — manually
5. Tracks every trade, signal, and PnL with full auditability

> ⚠️ **This is NOT an auto-trading bot.** The system informs and alerts. The human decides and executes.

---

## 🏁 END TARGET (FINAL PRODUCT)

The system's final deliverable is a **real-time trade alert on a dashboard** with all the information the trader needs to act:

```
Raw Data → Features → 10-Model Ensemble → 7-Strategy Prediction → Signal Filter → 🔔 TRADER ALERTED
                                                                                          ↓
                                                                              Trader Reviews Signal
                                                                                          ↓
                                                                             Trader Clicks BUY / SHORT
```

### What "Done" Looks Like:
- Market opens at 9:15 AM
- System fetches live OHLCV data automatically
- All 7 strategies run **in parallel** for all Nifty50 stocks
- A **Regime Classifier** decides which strategies are valid today
- Each active strategy scores every stock using the 10-model ensemble
- Signals passing the filter appear on the **Frontend Dashboard as alerts**
- Trader sees: Symbol, Direction, Entry, Stop Loss, L1, L2, L3 targets, Confidence
- Trader clicks **BUY** or **SHORT SELL** (or ignores the signal)
- System logs the decision and tracks PnL if trader acted

---

## ⚠️ CRITICAL WARNINGS — READ BEFORE WRITING ANY CODE

> **THIS IS A REAL MONEY SYSTEM. EVERY BUG CAN COST REAL RUPEES.**

- ❌ Never hardcode prices, quantities, or symbols
- ❌ Never place an order without position size validation
- ❌ Never skip stop-loss calculation
- ❌ Never run untested models on live data
- ❌ Never bypass the Signal Filter thresholds
- ✅ Every trade MUST be logged before execution
- ✅ Every model change MUST be validated on historical data first
- ✅ Walk-forward validation ONLY — no look-ahead bias

---

## 📊 CURRENT PROJECT STATE (April 2026)

| Component | Status | Notes |
|-----------|--------|-------|
| Data Ingestion | ✅ Done | Nifty50 parquet → PostgreSQL via `sync_data.py` |
| Target Engineering | ✅ Done | ML targets (MAE/MFE) quantified |
| Model Service | ✅ Done | FastAPI + 10-model ensemble (XGB, CatBoost, etc.) |
| Signal Service | ✅ Done | 7 strategies + Regime Classifier implemented |
| News Service | ✅ Done | RSS-based headline ingestion for all Nifty symbols |
| Fundamental Service | ✅ Done | PE, Market Cap, and 52W metrics via yfinance |
| AI Service (Gemma) | ✅ Done | Local LLM intelligence for decision support |
| Frontend Dashboard | ✅ Done | TypeScript React with Unified Stock Page |

**Data**: ~50 Nifty stocks × 1-min OHLCV with **70 enriched features** in PostgreSQL.

---

## 🏗️ SYSTEM ARCHITECTURE

### Services (Independent Microservices)

| Service | Port | Responsibility |
|---------|------|----------------|
| **Gateway** | 8000 | Single entry point — all API routing |
| **Frontend (React)** | 3000 | TypeScript-based Dashboard + Stock Page |
| **Data Service** | 7001 | Live data ingestion + DB retrieval |
| **Feature Service** | 7002 | Real-time feature computation |
| **Model Service** | 7003 | 10-model ensemble + 7 strategies |
| **Signal Service** | 7004 | Regime classifier + signal filtering |
| **News Service** | 7007 | RSS-based headline ingestion |
| **Fundamental Svc** | 7008 | yfinance/Angel fundamentals ingestion |
| **Institutional Svc** | 7009 | Symbol-specific delivery + FII metrics |
| **Sentiment Svc** | 7010 | TextBlob scoring of market news |
| **AI Service** | 7011 | Gemma 2B decision support |

### Strict Data Flow (MUST FOLLOW THIS ORDER)

```
[Data Service] ──→ [Feature Service] ──→ [Model Service]
                                               │
                                               ↓
                                       [Signal Service]
                                               │
             ┌─────────────────────────────────┘
             ↓
    [Execution Service] ──→ [Monitoring Service]
```

---

## 🧠 THE 7-STRATEGY SYSTEM (CORE OF THE SYSTEM)

All **7 strategies run in parallel** for every stock. The **Regime Classifier (Strategy 7)** determines which strategies are active based on market conditions. The **Signal Service** picks the best-scoring active signal.

### Strategy 1: Opening Range Breakout (ORB)
**Used by**: Most major quant funds for the first 30 minutes of trade.

- Detects breakouts above/below the first 15-minute high/low
- Validates with volume confirmation
- **Direction**: LONG only (above range), SHORT only (below range)
- **Key Fields**: `day_open`, `minutes_from_open`, `ATR_14`, `volume_spike_ratio`

### Strategy 2: VWAP Mean Reversion
**Used by**: Citadel, Virtu, IMC — institutional market makers.

- Trades when price deviates > 1.5 ATR from VWAP and shows reversal signals
- **Direction**: LONG when oversold below VWAP, SHORT when overbought above VWAP
- **Key Fields**: `vwap`, `distance_from_vwap`, `ATR_14`, `RSI_14`, `Bollinger_%B`

### Strategy 3: Intraday Momentum
**Used by**: Two Sigma, DE Shaw — systematic momentum programs.

- Identifies continuation moves when RSI, MACD, and price action align
- Enters in the direction of the established intraday trend
- **Direction**: LONG and SHORT
- **Key Fields**: `Return_Lag_1`, `Return_5D`, `MACD_Hist`, `ADX_14`, `OBV_Slope_10`

### Strategy 4: Relative Strength (Sector Rotation)
**Used by**: Millennium Management, Point72, Balyasny.

- Longs the top-performing stock in the top-performing sector vs Nifty
- **Direction**: LONG only
- **Key Fields**: `relative_strength`, `sector_strength`, `nifty_return`, `return_percentile`, `volume_percentile`

### Strategy 5: Volatility Squeeze Breakout
**Used by**: Renaissance Technologies, AQR.

- Detects Bollinger Band compression (low volatility) before explosive move
- Enters on the first break of the squeeze in the direction of breakout
- **Direction**: LONG and SHORT (follow the break)
- **Key Fields**: `Volatility_20D`, `ATR_14`, `Bollinger_%B`, `RVOL_20`, `Wavelet_Return`

### Strategy 6: Volume Spike Reversal (Exhaustion Move)
**Used by**: Jane Street, Susquehanna International Group.

- Fades exhaustion moves after massive volume spikes on extended candles
- Industry standard: **both long and short** — fade extreme moves in either direction
- **Direction**: LONG and SHORT (counter-trend)
- **Key Fields**: `volume_spike_ratio`, `RVOL_20`, `RSI_14`, `CMF_20`, `range_pct`

### Strategy 7: Market Regime Classifier (Meta-Strategy)
**Used by**: All top quant funds as the control layer.

Detects which market regime is active and enables/disables strategies accordingly:

| Regime | Condition | Active Strategies |
|--------|-----------|-------------------|
| **Trending** | ADX > 25, Volatility High | ORB, Momentum |
| **Range-Bound** | ADX < 20 | VWAP Reversion, Volume Reversal |
| **Breakout Ready** | Vol Contracting, ADX Rising | Volatility Squeeze |
| **Strong Sector** | Any Regime | Relative Strength |

- **Key Fields**: `ADX_14`, `Volatility_20D`, `ATR_14`, `MACD_Hist`, `nifty_return`

---

## 🤖 THE 10-MODEL ML ENSEMBLE

Every active strategy uses the **same 10-model ensemble** to score its trade signals. Models are trained separately for **classification** (probability) and **regression** (return/drawdown).

| Model | Type | Predicts |
|-------|------|---------|
| Logistic Regression | Classification | Probability |
| Ridge Regression | Regression | Return / Drawdown |
| Naive Bayes | Classification | Probability |
| Random Forest | Both | Probability + Return |
| XGBoost | Both | Probability + Return |
| LightGBM | Both | Probability + Return |
| CatBoost | Both | Probability + Return |
| SVM | Classification | Probability |
| Isolation Forest | Anomaly Detection | Is market condition normal? |
| Meta Ensemble | Stacking | Final aggregated score |

### Prediction Output (Per Strategy, Per Stock)

```json
{
  "strategy": "ORB",
  "symbol": "RELIANCE",
  "probability": 0.78,
  "expected_return": 1.1,
  "expected_drawdown": 0.4,
  "confidence": 0.82,
  "regime": "Trending"
}
```

---

## ⚔️ SIGNAL FILTER (STRICT — NO EXCEPTIONS)

Signal Service applies this filter to EVERY strategy output before **alerting the trader**:

```
IF:
  probability > 0.70
  AND expected_return > 0.8R
  AND expected_drawdown < 0.5R
  AND regime allows this strategy

THEN:
  ALERT TRADER ON DASHBOARD
ELSE:
  DISCARD (do not show)
```

---

## 📐 TRADE LEVEL SYSTEM (L1 / L2 / L3)

Every signal shown on the dashboard MUST include **3 profit-booking levels** and a **stop loss**. This is the core display format for the trader.

### Entry Directions
- **BUY** — Long position (price expected to go up)
- **SHORT SELL** — Short position (price expected to go down)

> Not all signals are automatic. The **trader decides** whether to act.

### Level Definitions

```
ENTRY  → Price at which the trader enters the trade

SL     → Stop Loss: Maximum loss the trader is willing to take
         SL = Entry - (1.0 × ATR_14)   [for BUY]
         SL = Entry + (1.0 × ATR_14)   [for SHORT]

L1     → First target: Close 40% of the position here (quick profit)
         L1 = Entry + (1.0 × ATR_14)   [for BUY]
         L1 = Entry - (1.0 × ATR_14)   [for SHORT]

L2     → Second target: Close 40% of the position here
         L2 = Entry + (2.0 × ATR_14)   [for BUY]
         L2 = Entry - (2.0 × ATR_14)   [for SHORT]

L3     → Final target: Close remaining 20% here (let the winner run)
         L3 = Entry + (3.5 × ATR_14)   [for BUY]
         L3 = Entry - (3.5 × ATR_14)   [for SHORT]
```

### Position Closing Rules (3 Levels Max)

```
At L1 → Close 40% of position
At L2 → Close 40% of position
At L3 → Close remaining 20%

AT 3:15 PM → Force close 100% whatever is still open (intraday rule)
If SL hit  → Close 100% immediately (no override)
```

### Final Signal Output (Dashboard Alert)

```json
{
  "symbol": "RELIANCE",
  "strategy": "ORB",
  "action": "BUY",
  "entry": 2450.00,
  "stop_loss": 2410.00,
  "L1": 2490.00,
  "L2": 2530.00,
  "L3": 2590.00,
  "probability": 0.78,
  "confidence": 0.82,
  "regime": "Trending",
  "timestamp": "2026-04-03T09:31:00+05:30",
  "status": "ALERT_PENDING_TRADER_ACTION"
}
```

> ⚠️ **`status` starts as `ALERT_PENDING_TRADER_ACTION`.** It only changes to `ACTIVE` when the trader manually clicks BUY or SHORT SELL on the dashboard.

---

## 🖥️ FRONTEND DASHBOARD — SIGNAL CARD (Required UI)

Each alert on the dashboard must show a **Signal Card** with:

```
┌─────────────────────────────────────────┐
│  🔔 RELIANCE   [ORB]   [BUY]           │
│                                         │
│  Entry:    ₹ 2450.00                    │
│  SL:       ₹ 2410.00  ⛔ (-40 pts)     │
│                                         │
│  L1:       ₹ 2490.00  ✅ (+40 pts)     │
│  L2:       ₹ 2530.00  ✅ (+80 pts)     │
│  L3:       ₹ 2590.00  ✅ (+140 pts)    │
│                                         │
│  Confidence: 82%  │  Strategy: ORB      │
│  Regime: Trending  │  9:31 AM            │
│                                         │
│  [  ✅ BUY  ]   [ ❌ SHORT ]   [SKIP]  │
└─────────────────────────────────────────┘
```

**Trader Actions:**
- **BUY** → Logs trade as active BUY position
- **SHORT SELL** → Logs trade as active SHORT position
- **SKIP** → Dismisses alert, logs as skipped

---



## 📉 TARGET ENGINEERING (MANDATORY BEFORE TRAINING)

Script: `scripts/calculate_targets.py`

For each ORB trade, compute:

```
Entry price       → ORB breakout price
Stop Loss         → Entry ± ATR_14
MFE               → Max Favorable Excursion (max profit reached)
MAE               → Max Adverse Excursion (max drawdown hit)
Return (R)        → MFE / ATR_14
Drawdown (R)      → MAE / ATR_14
Probability Label → 1 if MFE > 1.0R, else 0
```

**Training Rule**: No data leakage. Use walk-forward validation only.

---

## 🗄️ DATABASE (POSTGRESQL — SINGLE SOURCE OF TRUTH)

### Tables

| Table | Purpose |
|-------|---------|
| `ohlcv_enriched` | 1-min OHLCV + 70 enriched features for all Nifty50 stocks |
| `features` | Real-time computed features |
| `strategy_signals` | Output from each of the 7 strategies |
| `trade_signals` | Filtered, execution-ready signals |
| `executions` | Every order placed with broker |
| `positions` | Open and closed positions |
| `pnl_log` | Per-trade PnL tracking |

### DB Rules

- ❌ No parquet files in production queries
- ❌ No direct DB access from frontend
- ❌ No schema changes without a migration script
- ✅ All timestamps stored as UTC in DB; converted to IST for display only
- ✅ Every trade must be logged to `executions` BEFORE the order is placed

---

## 📦 DATA

### Current Data

| Dataset | Location | Stocks | Status |
|---------|----------|--------|--------|
| Enriched Nifty50 (raw) | `data/enriched_data_v2_nifty50/` | 50 | Source |
| Model-ready (with targets) | `data/mode_ready_data/` | ~13 processed | 🔄 In Progress |

### 70 Feature Fields (Key Groups)

| Group | Fields |
|-------|--------|
| OHLCV | `open, high, low, close, volume` |
| Price Dynamics | `returns, prev_close, range, range_pct` |
| VWAP | `vwap, cum_vol, distance_from_vwap` |
| Volume | `volume_zscore, volume_spike_ratio, RVOL_20, OBV_Slope_10` |
| Momentum | `RSI_14, MACD_Hist, STOCH_k_14, Return_Lag_1, Return_5D` |
| Volatility | `ATR_14, Volatility_20D, Bollinger_%B, Wavelet_Return` |
| Market Context | `nifty_return, banknifty_return, relative_strength` |
| Sector | `sector, sector_return, sector_strength` |
| Ranking | `return_rank, volume_rank, return_percentile` |
| Time | `minutes_from_open, minutes_to_close, day_of_week` |
| Targets | `Target` (from parquet), `target_mfe`, `target_mae`, `target_prob` |

---

## 🔌 API CONTRACT (ALL SERVICES)

### Standard Response Format

```json
{
  "status": "success | error",
  "data": {},
  "error": null
}
```

- JSON only. No HTML responses.
- No breaking changes to existing endpoints.
- Version APIs (`/v2/...`) if contracts change.

---

## 📈 FRONTEND — MULTI-PAGE DASHBOARD

- **Framework**: React + Vite (port 3000)
- **Charts**: TradingView Lightweight Charts (preferred) or Recharts
- **Rules**: No business logic. No direct DB. API Gateway only.
- **Pages**: 5 pages total

---

### 📊 How Many Stocks Get Activated Per Day?

With **50 Nifty stocks** and **7 strategies** running in parallel, here's the realistic expectation:

| Market Condition | Active Strategies | Estimated Alerts/Day |
|-----------------|-------------------|---------------------|
| Strong Trending Day | ORB + Momentum + Relative Strength | 8–15 stocks |
| Range-Bound Day | VWAP Reversion + Volume Reversal | 6–12 stocks |
| Volatile/Breakout Day | Squeeze Breakout + ORB | 5–10 stocks |
| Mixed Day | All 7 active, split signals | 10–20 stocks |

> **Typical day: 8–15 high-confidence alerts from 50 stocks.**
> Of those, the trader may act on 3–5 based on personal judgment.

If expanded to **500 stocks**: ~80–150 alerts/day expected.

---

### 🎯 Daily Profit Target: Reality Check

| Target | Realism | Notes |
|--------|---------|-------|
| **1–3% per day** | Extremely ambitious | That's 250–750% annually — Renaissance-level |
| **0.3–0.8% per day** | Achievable on good days | 75–200% annually with compounding |
| **15–25% per year** | Industry standard (top quant funds) | Realistic for a systematic system |
| **First goal** | Beat Nifty index returns (~12–15% yr) | Prove the system has edge |

> ⚠️ **Be realistic.** A system that catches 3–5 trades per day with avg 0.5R win = very good.
> Start with the goal: **Win rate > 55%, Avg R:R > 1.5:1**. Profit follows.

---

### 🖥️ Page 1: Main Dashboard (Index View)

**Route**: `/`

**Purpose**: At-a-glance view of the entire market for today.

```
┌────────────────────────────────────────────────────────────┐
│  🚀 Trading System          [Today: April 3] [9:31 AM IST] │
├────────────────┬───────────────────────────────────────────┤
│  TODAY         │  📈 Nifty 50: 22,450  (+0.3%)            │
│  Regime: TREND │  💹 BankNifty: 48,200 (-0.1%)            │
│  Active Strat: │                                           │
│   ORB ✅       │  Day P&L:  + ₹ 4,200  (active: 2 trades) │
│   Momentum ✅  │  Signals Today: 12 total  (5 acted on)    │
│   Rel Str ✅   │  Win/Loss: 3W / 1L / 1 Open              │
├────────────────┴───────────────────────────────────────────┤
│  🔔 LIVE ALERTS (new signals appear here in real time)     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 🔔 RELIANCE  [ORB] [BUY]  82%  Entry:2450 SL:2410  │  │
│  │    L1:2490  L2:2530  L3:2590       [BUY][SHORT][SKIP]│  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ 🔔 HDFCBANK  [VWAP REV] [SHORT] 74% Entry:1620...   │  │
│  └──────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────┤
│  📊 Active Positions                                        │
│  SBIN  [BUY]  Entry:780  SL:760  At L1 (hit) ✅  Open 60% │
└────────────────────────────────────────────────────────────┘
```

**Key Widgets**:
- Live Nifty/BankNifty price + change
- Today's regime badge (Trending / Range / Breakout)
- Which of the 7 strategies are active today
- Day P&L summary
- **Live alert feed** — real-time signal cards as they fire
- Active positions tracker with level status

---

### 📋 Page 2: Signals Page (All Today's Alerts)

**Route**: `/signals`

**Purpose**: Full list of all signals generated today. Filter, sort, and act.

```
┌──────────────────────────────────────────────────────────────┐
│  📋 Signals — April 3, 2026         Total: 12 │ Acted: 5    │
│                                                              │
│  Filter: [All ▼] [BUY] [SHORT] [ORB] [VWAP] [Momentum]...  │
│  Sort by: [Confidence ▼]                                     │
├──────────────────────────────────────────────────────────────┤
│  Symbol   │ Strategy │ Dir   │ Conf │ Entry  │ SL    │ L1–L3 │
│  RELIANCE │ ORB      │ BUY   │ 82%  │ 2450   │ 2410  │ View  │
│  HDFCBANK │ VWAP Rev │ SHORT │ 74%  │ 1620   │ 1640  │ View  │
│  SBIN     │ Momentum │ BUY   │ 78%  │ 781    │ 762   │ View  │
│  ...                                                         │
└──────────────────────────────────────────────────────────────┘
```

**Features**:
- Filter by strategy, direction, status (pending/acted/skipped)
- Click any row → opens Stock Page for that signal
- Confidence color coding (green > 80%, yellow 70–80%)
- Shows which level has been hit for acted signals

---

### 📈 Page 3: Stock Page (Per-Stock Deep Dive)

**Route**: `/stock/:symbol`

**Purpose**: Everything about one stock for today. All 7 strategy outputs + 10-model breakdown.

```
┌──────────────────────────────────────────────────────────────┐
│  RELIANCE    ₹ 2455.20  (+0.8%)          April 3, 2026       │
├─────────────────────────────────┬────────────────────────────┤
│                                 │  📐 Active Signal           │
│  [1-min Candlestick Chart]      │  Strategy: ORB              │
│                                 │  Direction: BUY ↑           │
│  Lines plotted on chart:        │  Entry:  ₹ 2450             │
│   ─ ─ SL  (red dashed)         │  SL:     ₹ 2410  ⛔          │
│   ─ ─ L1  (yellow)             │  L1:     ₹ 2490  ✅ (hit)   │
│   ─ ─ L2  (green)              │  L2:     ₹ 2530  ⏳          │
│   ─ ─ L3  (blue)               │  L3:     ₹ 2590  ⏳          │
│                                 │  Confidence: 82%            │
├─────────────────────────────────┴────────────────────────────┤
│  🤖 7-Strategy Scores for Today                              │
│                                                              │
│  Strategy          │ Signal │ Probability │ R:R   │ Status   │
│  ORB               │ BUY    │    78%      │ 2.8   │ ✅ Alert │
│  VWAP Reversion    │ —      │    48%      │  —    │ ❌ Below │
│  Intraday Momentum │ BUY    │    71%      │ 2.1   │ ✅ Alert │
│  Relative Strength │ BUY    │    80%      │ 2.4   │ ✅ Alert │
│  Vol Squeeze       │ —      │    32%      │  —    │ ❌ Below │
│  Volume Reversal   │ —      │    55%      │  —    │ ❌ Below │
│  Regime Classifier │ TREND  │    —        │  —    │ Trending │
├──────────────────────────────────────────────────────────────┤
│  🧠 10-Model Ensemble Breakdown (for ORB signal)            │
│                                                              │
│  Model              │ Prob  │ Ret Estimate │ Drawdown Est   │
│  Logistic Reg       │ 0.76  │    1.05R     │   0.38R        │
│  Ridge Reg          │  —    │    1.12R     │   0.41R        │
│  Naive Bayes        │ 0.71  │     —        │    —           │
│  Random Forest      │ 0.80  │    1.20R     │   0.35R        │
│  XGBoost            │ 0.82  │    1.18R     │   0.32R        │
│  LightGBM           │ 0.79  │    1.15R     │   0.36R        │
│  CatBoost           │ 0.78  │    1.10R     │   0.40R        │
│  SVM                │ 0.74  │     —        │    —           │
│  Isolation Forest   │ NORMAL│     —        │    —  ← no anomaly │
│  Meta Ensemble      │ 0.78  │    1.10R     │   0.40R ← FINAL│
└──────────────────────────────────────────────────────────────┘
```

---

### 📂 Page 4: Positions Page

**Route**: `/positions`

**Purpose**: All trades the user has acted on. Live status of each level.

```
┌───────────────────────────────────────────────────────────┐
│  📂 Positions — April 3, 2026                             │
├─────────────────────────────────────────────────────────┤
│  SBIN  [BUY]  Entry:781  SL:762  Qty:50              │
│  L1: ✅ Hit @ 800  (sold 20 qty)                       │
│  L2: ⏳ 819  (pending 20 qty)                          │
│  L3: ⏳ 835  (pending 10 qty)                          │
│  Current P&L:  +₹ 950 (unrealised)                    │
│                                [Close All Now]         │
├─────────────────────────────────────────────────────────┤
│  RELIANCE [BUY] Entry:2450 → L1 (closed, +₹ 800 done) │
│  [CLOSED]                                              │
└───────────────────────────────────────────────────────┘
```

**Features**:
- Shows which levels (L1/L2/L3) have been hit
- Manual "Close All" button for each position
- For each closed position: final P&L shown
- Daily summary at top: Total P&L, win%, avg hold time

---

### 📉 Page 5: Analytics Page (Daily/Historical)

**Route**: `/analytics`

**Purpose**: How well the system is performing. Per strategy, per model.

```
┌──────────────────────────────────────────────────────────┐
│  📉 Analytics                 [Today] [Week] [Month]     │
│                                                          │
│  Overall Win Rate:   62%     Avg R:R:  1.8:1            │
│  Total Signals:      145     Acted On: 38   Skipped: 107 │
│  Net P&L (Month):  +₹ 28,400                            │
├──────────────────────────────────────────────────────────┤
│  Per-Strategy Performance                                │
│  Strategy          │ Signals │ Win% │ Avg Return │ Avg RR │
│  ORB               │   42    │ 64%  │   1.1R     │  1.9   │
│  VWAP Reversion    │   38    │ 58%  │   0.9R     │  1.6   │
│  Momentum          │   28    │ 67%  │   1.2R     │  2.1   │
│  Relative Strength │   22    │ 70%  │   1.3R     │  2.3   │
│  Vol Squeeze       │   10    │ 60%  │   1.5R     │  2.8   │
│  Volume Reversal   │    5    │ 40%  │   0.7R     │  1.2   │
└──────────────────────────────────────────────────────────┘
```

---

### Frontend Navigation Structure

```
/                   ← Dashboard (live alerts + positions + regime)
/signals            ← All signals today (filterable)
/stock/:symbol      ← Per-stock: chart + 7 strategies + 10 models
/positions          ← Active + closed positions + P&L
/analytics          ← Performance stats by strategy/model
```

---

## 🎨 FRONTEND LAYOUT DESIGN SYSTEM

### Design Philosophy
- **Dark theme** — professional trading terminal aesthetic (black/dark gray base)
- **Color-coded everything** — BUY = green, SHORT = red, Neutral = blue/gray
- **Dense but readable** — traders need a lot of data at once, no wasted space
- **Real-time feel** — subtle animations on new alerts, live price tickers

---

### 🎨 Color Palette

```
Background:        #0A0E1A   (deep navy black)
Surface/Cards:     #111827   (dark gray)
Border:            #1F2937   (subtle divider)

BUY / Profit:      #10B981   (emerald green)
SHORT / Loss:      #EF4444   (red)
Warning / SL:      #F59E0B   (amber)
Info / Neutral:    #3B82F6   (blue)
Pending:           #8B5CF6   (purple)

Text Primary:      #F9FAFB   (white)
Text Secondary:    #9CA3AF   (gray-400)
Text Muted:        #4B5563   (gray-600)

L1 Target:         #FBBF24   (yellow)
L2 Target:         #34D399   (light green)
L3 Target:         #60A5FA   (sky blue)
```

---

### 📐 Typography

```
Font Family:   'JetBrains Mono' (numbers/prices) + 'Inter' (labels/text)
               Import both from Google Fonts

Heading:       Inter 700, 18-24px
Label:         Inter 500, 12-14px
Price:         JetBrains Mono 600, 16-20px
Badge:         Inter 600, 10-11px, uppercase, letter-spacing 0.05em
```

---

### 🧱 Global Layout Shell

Every page uses the same shell:

```
┌──────────────────────────────────────────────────────────────────┐
│  TOP NAV BAR (fixed, 56px height)                                │
│  [🚀 TradingSystem]  [Dashboard] [Signals] [Positions] [Analytics]│
│                      [🟢 Market Open]  [Nifty: 22,450 +0.3%]    │
├──────────────┬───────────────────────────────────────────────────┤
│              │                                                    │
│  LEFT        │   MAIN CONTENT AREA                               │
│  SIDEBAR     │   (page-specific)                                  │
│  (240px)     │                                                    │
│              │                                                    │
│  Today's     │                                                    │
│  Regime      │                                                    │
│  ─────────   │                                                    │
│  Strategies  │                                                    │
│  Active      │                                                    │
│  ─────────   │                                                    │
│  Quick PnL   │                                                    │
│  ─────────   │                                                    │
│  Stock List  │                                                    │
│  (Nifty 50)  │                                                    │
│              │                                                    │
└──────────────┴───────────────────────────────────────────────────┘
```

**Top Nav**: Fixed, dark, shows live Nifty/BankNifty price with color change animation.
**Left Sidebar**: Always visible. Shows regime, which strategies are live, daily PnL, quick-nav stock list.

---

### 🖥️ Layout — Page 1: Dashboard (`/`)

```
TOP NAV
├── LEFT SIDEBAR (fixed)
└── MAIN CONTENT (3-column grid on desktop, stacked on mobile)
    │
    ├── ROW 1: STAT CARDS (4 cards, equal width)
    │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │   │ Regime   │ │ Today's  │ │ Signals  │ │ Win Rate │
    │   │ TRENDING │ │ P&L      │ │ 12 fired │ │ Today    │
    │   │ 🟢       │ │ +₹4,200  │ │ 5 acted  │ │  3W / 1L │
    │   └──────────┘ └──────────┘ └──────────┘ └──────────┘
    │
    ├── ROW 2: TWO COLUMNS
    │   ┌─────────────────────────┐  ┌──────────────────────┐
    │   │ 🔔 LIVE ALERT FEED      │  │ 📊 ACTIVE POSITIONS  │
    │   │ (scrollable card list)  │  │ SBIN BUY ✅L1 ⏳L2  │
    │   │                         │  │ HDFCBANK SHORT ⏳L1  │
    │   │ [Signal Card]           │  │                      │
    │   │ [Signal Card]           │  │ Total Open P&L:      │
    │   │ [Signal Card]           │  │ +₹ 2,100             │
    │   │ [Load More...]          │  └──────────────────────┘
    │   └─────────────────────────┘
    │
    └── ROW 3: NIFTY 50 HEATMAP
        ┌──────────────────────────────────────────────────┐
        │ 🟩 RELIANCE  🟩 HDFCBANK  🟥 SBIN  🟩 TCS ...  │
        │ (color = today's return %, click → stock page)   │
        └──────────────────────────────────────────────────┘
```

---

### 🖥️ Layout — Page 2: Signals (`/signals`)

```
TOP NAV
└── MAIN CONTENT (full width, no sidebar on this page)
    │
    ├── FILTER BAR (sticky)
    │   [Date: Today ▼]  [Strategy: All ▼]  [Dir: All ▼]
    │   [Status: All ▼]  [Min Conf: 70% ▼]  [🔍 Search]
    │
    └── SIGNAL TABLE (sortable columns)
        ┌──────┬──────────┬──────┬──────┬───────┬────┬────┬────┬────────┐
        │Symbol│ Strategy │ Dir  │ Conf │ Entry │ SL │ L1 │ L2 │ L3     │
        ├──────┼──────────┼──────┼──────┼───────┼────┼────┼────┼────────┤
        │RELIAN│ ORB      │ 🟢BUY│ 82%  │ 2450  │2410│2490│2530│2590 [>]│
        │HDFC  │ VWAP Rev │ 🔴SHT│ 74%  │ 1620  │1640│1580│1540│1500 [>]│
        │SBIN  │ Momentum │ 🟢BUY│ 78%  │  781  │ 762│ 800│ 819│ 835 [>]│
        └──────┴──────────┴──────┴──────┴───────┴────┴────┴────┴────────┘
        Rows: color-coded (green row for BUY, red-tinted for SHORT)
        Click row → opens /stock/:symbol with that signal highlighted
```

---

### 🖥️ Layout — Page 3: Stock Page (`/stock/:symbol`)

```
TOP NAV
└── MAIN CONTENT (2-column layout)
    │
    ├── LEFT COLUMN (65% width)
    │   ┌──────────────────────────────────────────────────┐
    │   │ CANDLESTICK CHART (TradingView widget, 1-min)    │
    │   │                                                  │
    │   │  SL line   ─ ─ ─ ─ ─ ─ ─ ─  [red dashed]      │
    │   │  L1 line   ─ ─ ─ ─ ─ ─ ─ ─  [yellow]          │
    │   │  L2 line   ─ ─ ─ ─ ─ ─ ─ ─  [green]           │
    │   │  L3 line   ─ ─ ─ ─ ─ ─ ─ ─  [blue]            │
    │   │  ENTRY     ━ ━ ━ ━ ━ ━ ━ ━  [white bold]       │
    │   └──────────────────────────────────────────────────┘
    │
    │   ┌──────────────────────────────────────────────────┐
    │   │ 7-STRATEGY SCORE TABLE                           │
    │   │ (horizontal table with colored probability bars) │
    │   │                                                  │
    │   │ ORB          ████████░░ 78%  BUY   R:R 2.8  ✅  │
    │   │ VWAP Rev     ████░░░░░░ 48%   —     —       ❌  │
    │   │ Momentum     ███████░░░ 71%  BUY   R:R 2.1  ✅  │
    │   │ Rel Strength ████████░░ 80%  BUY   R:R 2.4  ✅  │
    │   │ Vol Squeeze  ███░░░░░░░ 32%   —     —       ❌  │
    │   │ Vol Reversal █████░░░░░ 55%   —     —       ❌  │
    │   │ Regime       TRENDING ← meta                    │
    │   └──────────────────────────────────────────────────┘
    │
    └── RIGHT COLUMN (35% width)
        ┌──────────────────────────────┐
        │ SIGNAL CARD (active signal)  │
        │ RELIANCE • ORB • BUY ↑       │
        │                              │
        │ Entry  ₹ 2450.00             │
        │ SL     ₹ 2410.00  ⛔ -40pts │
        │ L1     ₹ 2490.00  🟡 +40pts │
        │ L2     ₹ 2530.00  🟢 +80pts │
        │ L3     ₹ 2590.00  🔵+140pts │
        │                              │
        │ Prob: 78%  Conf: 82%         │
        │ Strategy: ORB  9:31 AM       │
        │                              │
        │ [✅ BUY] [🔴 SHORT] [SKIP]  │
        ├──────────────────────────────┤
        │ 10-MODEL BREAKDOWN           │
        │ (compact table)              │
        │ LogReg    0.76  1.05R  0.38R │
        │ Ridge      —   1.12R  0.41R │
        │ NaiveBayes 0.71  —      —   │
        │ RF        0.80  1.20R  0.35R│
        │ XGBoost   0.82  1.18R  0.32R│
        │ LightGBM  0.79  1.15R  0.36R│
        │ CatBoost  0.78  1.10R  0.40R│
        │ SVM       0.74   —      —   │
        │ IsoForest NORMAL             │
        │ ━━━━━━━━━━━━━━━━━━━━━━━━━━  │
        │ META:     0.78  1.10R  0.40R│
        └──────────────────────────────┘
```

---

### 🖥️ Layout — Page 4: Positions (`/positions`)

```
TOP NAV
└── MAIN CONTENT
    │
    ├── SUMMARY BAR
    │   [ Open: 2 positions ]  [ Closed today: 3 ]
    │   [ Realised P&L: +₹ 2400 ]  [ Unrealised: +₹ 950 ]
    │   [ Total Today: +₹ 3350 ]
    │
    ├── OPEN POSITIONS (cards)
    │   ┌────────────────────────────────────────────────┐
    │   │ SBIN  [ORB]  BUY ↑                  [🔴 CLOSE]│
    │   │ Entry: ₹781  │  Qty: 50  │  P&L: +₹950        │
    │   │                                                │
    │   │ SL  ━━━━━━━━━━━━━━━━━ ₹ 762   [ Active ]      │
    │   │ L1  ██████████████░░░ ₹ 800   [✅ HIT — 20qty]│
    │   │ L2  ░░░░░░░░░░░░░░░░ ₹ 819   [ Pending ]      │
    │   │ L3  ░░░░░░░░░░░░░░░░ ₹ 835   [ Pending ]      │
    │   │                                                │
    │   │ Current Price: ₹ 809  ↑  Time: 11:42 AM        │
    │   └────────────────────────────────────────────────┘
    │
    └── CLOSED POSITIONS (table)
        ┌──────┬────────┬───────┬──────┬──────┬─────────┐
        │Symbol│ Dir    │ Entry │ Exit │ P&L  │ Levels   │
        │RELIAN│ BUY ✅ │ 2450  │ 2490 │+₹800 │ L1 hit  │
        │HDFC  │ SHORT ✅│ 1620  │ 1640 │-₹400 │ SL hit  │
        └──────┴────────┴───────┴──────┴──────┴─────────┘
```

---

### 🖥️ Layout — Page 5: Analytics (`/analytics`)

```
TOP NAV
└── MAIN CONTENT (dashboard grid)
    │
    ├── ROW 1: TIME FILTER + TOP KPIs
    │   [Today] [This Week] [This Month] [Custom Range]
    │
    │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │   │ Win Rate │ │ Avg R:R  │ │ Signals  │ │ Net P&L  │
    │   │   62%    │ │  1.8:1   │ │  145 tot │ │ +₹28,400 │
    │   └──────────┘ └──────────┘ └──────────┘ └──────────┘
    │
    ├── ROW 2: TWO COLUMNS
    │   ┌────────────────────────┐ ┌───────────────────────┐
    │   │ STRATEGY PERFORMANCE   │ │ P&L OVER TIME (chart) │
    │   │ (bar chart per strat)  │ │ Line chart, daily PnL │
    │   │                        │ │ Cumulative PnL curve  │
    │   │ ORB    ████████ 64%    │ │                       │
    │   │ Momentum██████ 67%     │ │                       │
    │   │ RelStr ████████ 70%    │ │                       │
    │   │ VWAP   ██████  58%     │ └───────────────────────┘
    │   │ Squeeze███████ 60%     │
    │   │ VolRev ████    40%     │
    │   └────────────────────────┘
    │
    └── ROW 3: MODEL ACCURACY TABLE
        ┌──────────────┬────────┬────────────┬───────────────┐
        │ Model        │ Win %  │ Avg Return │ Avg Drawdown  │
        │ XGBoost      │  68%   │    1.2R    │    0.35R      │
        │ LightGBM     │  66%   │    1.15R   │    0.36R      │
        │ Random Forest│  65%   │    1.1R    │    0.38R      │
        │ Meta Ensemble│  70%   │    1.3R    │    0.33R      │
        └──────────────┴────────┴────────────┴───────────────┘
```

---

### 📱 Responsive Breakpoints

| Breakpoint | Layout |
|------------|--------|
| Desktop (> 1280px) | Full layout with sidebar + multi-column grids |
| Tablet (768–1280px) | Sidebar collapses to icon-only; 2-column grids |
| Mobile (< 768px) | No sidebar (hamburger menu); single column stack |

> ⚠️ Trading is done on desktop. Mobile is view-only (no BUY/SHORT buttons on mobile).

---

### 🧩 Reusable Components

```
<SignalCard />        ← The L1/L2/L3 alert card (used on Dashboard + Signals page)
<ModelTable />        ← 10-model breakdown table (used on Stock page)
<StrategyScoreBar />  ← Progress-bar row for each strategy (Stock page)
<LevelTracker />      ← SL / L1 / L2 / L3 progress bar (Positions page)
<RegimeBadge />       ← Trending / Range / Breakout pill badge
<PriceTicket />       ← Live price display with color (green/red)
<PnLSummary />        ← Daily P&L card (Dashboard + Positions)
<HeatmapGrid />       ← Nifty 50 color heatmap (Dashboard)
```

---

## 💰 EXECUTION SERVICE (MOST CRITICAL)

- **DO NOT** add model logic here
- **DO NOT** add feature computation here
- **MUST HAVE**:
  - Pre-trade order validation (price, quantity, symbol)
  - Position size calculation (risk-based)
  - Stop-loss and target verification before order placement
  - Retry logic for failed orders (max 3 retries)
  - Full trade logging to DB before and after execution

---

## 📁 FOLDER STRUCTURE

```
trading-system/
├── data/
│   ├── enriched_data_v2_nifty50/   ← Source parquet files (Nifty50)
│   └── mode_ready_data/            ← Parquet with MFE/MAE targets
│
├── scripts/
│   ├── ingest_nifty50.py           ← Parquet → PostgreSQL (running)
│   ├── calculate_targets.py        ← ORB target engineering (running)
│   └── init_nifty50_db.py          ← DB schema initialization
│
├── services/
│   ├── data-service/               ← Port 7001 (not started)
│   ├── feature-service/            ← Port 7002 (not started)
│   ├── model-service/              ← Port 7003 (skeleton done)
│   │   ├── app/
│   │   │   ├── main.py             ← FastAPI entry
│   │   │   ├── models/             ← 10 ML agents
│   │   │   │   ├── base.py
│   │   │   │   ├── linear.py
│   │   │   │   ├── tree.py
│   │   │   │   ├── kernel.py
│   │   │   │   ├── anomaly.py
│   │   │   │   └── meta.py
│   │   │   └── schemas/
│   │   └── requirements.txt
│   ├── signal-service/             ← Port 7004 (not started)
│   ├── execution-service/          ← Port 7005 (not started)
│   └── monitoring-service/         ← Port 7006 (not started)
│
├── gateway/                        ← Port 8000 (not started)
├── frontend/                       ← Port 3000 (running)
├── models/                         ← Saved .joblib model files
└── trading-system/                 ← Python virtual environment
```

---

## 🚀 DEVELOPMENT PHASES

### ✅ Phase 0 — Data Foundation (In Progress)
- [x] Ingest Nifty50 1-min OHLCV into PostgreSQL
- [ ] Complete MFE/MAE target engineering for all 50 stocks
- [ ] Validate data quality and timestamp consistency

### 🔲 Phase 1 — Core ML Pipeline
- [ ] Train 10-model ensemble on ORB strategy targets
- [ ] Save models to `models/` directory
- [ ] Build `/predict` endpoint in model-service
- [ ] Build 7 strategy modules in model-service

### 🔲 Phase 2 — Signal Engine
- [ ] Build Signal Service with Regime Classifier
- [ ] Implement parallel strategy evaluation
- [ ] Implement signal filter (probability > 0.7, etc.)
- [ ] Store signals in `strategy_signals` and `trade_signals` tables

### 🔲 Phase 3 — Execution
- [ ] Build Execution Service with broker API integration
- [ ] Implement position sizing and risk management
- [ ] Pre-trade validation and stop-loss enforcement

### 🔲 Phase 4 — Monitoring + Frontend
- [ ] Build Monitoring Service (real-time PnL, alerts)
- [ ] Build Gateway (API routing)
- [ ] Complete Frontend Dashboard (signals, positions, PnL)

### 🔲 Phase 5 — Live Trading
- [ ] Paper trading validation (2 weeks minimum)
- [ ] Live deployment with circuit breakers
- [ ] Continuous model retraining pipeline

---

## ▶️ RUNNING SERVICES

```bash
# Activate virtual environment
source trading-system/bin/activate

# Data ingestion (already running)
python scripts/ingest_nifty50.py

# Target engineering (already running)
python scripts/calculate_targets.py

# Model service
cd services/model-service
uvicorn app.main:app --port 7003 --reload

# Frontend
cd frontend
npm run dev -- --host
```

---

## 🔐 ABSOLUTE SAFETY RULES

1. **Never** deploy a model trained today to live trading the same day
2. **Never** place an order without first validating against `positions` table (avoid duplicate positions)
3. **Always** paper trade a new strategy for at least 10 trading days before going live
4. **Always** have a hard daily loss limit (e.g., stop all trading if daily loss > 2% of capital)
5. **Always** validate signals against broker's risk APIs before submitting
6. **Log everything** — signal, decision, order, fill, slippage, final PnL

---

## 🧠 FINAL PRINCIPLE

This system is built for one purpose: **to generate consistent, risk-adjusted returns with institutional-grade discipline.**

**Focus on**:
- Data integrity first, always
- Correct risk-reward targets
- Strategies that top hedge funds use and trust
- Auditability of every decision

**Do NOT**:
- Over-engineer features you cannot explain
- Add complexity without measurable backtested edge
- Touch execution logic without a complete test run
- Skip the signal filter, even if the trade "looks good"
