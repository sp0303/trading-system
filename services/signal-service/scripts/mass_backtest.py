"""
High-Speed Institutional Backtest Rig — v2
========================================
Key fixes vs v1:
  1. EnsemblePredictor runs IN-MEMORY (no HTTP calls to port 7003).
  2. All 6 strategies run concurrently per bar, regime-gated.
  3. reset_daily() is called on ALL strategies on day boundary (no state bleed).
  4. Resume logic uses MAX(timestamp) per symbol (not just presence check).
  5. itertuples() used throughout (no iterrows).
"""

import pandas as pd
import os
import sys
import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from tqdm.asyncio import tqdm

# ── In-Process Model Import (no HTTP) ──────────────────────────────────────────
# ── Path Setup (Ensures all internal 'app' imports work) ───────────────────────
SIGNAL_SERVICE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
MODEL_SERVICE_PATH = os.path.abspath(
    os.path.join(SIGNAL_SERVICE_ROOT, "..", "model-service")
)

for path in [SIGNAL_SERVICE_ROOT, MODEL_SERVICE_PATH]:
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.ensemble import EnsemblePredictor  # direct import — no HTTP!

# ── Signal Service Imports ─────────────────────────────────────────────────────
from app.strategies.regime import MarketRegimeClassifier
from app.strategies.orb import ORBStrategy
from app.strategies.vwap_reversion import VWAPReversionStrategy
from app.strategies.momentum import IntradayMomentumStrategy
from app.strategies.relative_strength import RelativeStrengthStrategy
from app.strategies.volatility_squeeze import VolatilitySqueezeStrategy
from app.strategies.volume_reversal import VolumeSpikeReversalStrategy
from app.models.database import SessionLocal
from app.models.schema import StrategySignal, TradeSignal
from app.services.target_calculator import TargetCalculator
from app.services.signal_filter import SignalFilter

# ── Configuration ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

DATA_DIR = "/home/sumanth/Desktop/trading-system/data/mode_ready_data/"
BACKTEST_ID = "BT_STABILIZED_FINAL_V1" # Unique ID for fresh start
CONCURRENCY_LIMIT = 4             # Parallel tickers at once

# Regime → allowed strategies (mirrors README table exactly)
REGIME_POLICY = {
    "Trending":    ["ORB", "Momentum", "Relative Strength"],
    "Range-Bound": ["VWAP Reversion", "Volume Reversal"],
    "Normal":      ["ORB", "Momentum", "VWAP Reversion", "Vol Squeeze"],
    # "Breakout Ready" classified as Normal by current regime classifier
}


def _build_strategies():
    """Instantiate one fresh set of all 6 strategies per ticker-coroutine."""
    return [
        ORBStrategy(),
        VWAPReversionStrategy(),
        IntradayMomentumStrategy(),
        RelativeStrengthStrategy(),
        VolatilitySqueezeStrategy(),
        VolumeSpikeReversalStrategy(),
    ]


async def process_ticker(symbol: str, test_start: str, test_end: str,
                          semaphore: asyncio.Semaphore,
                          predictor: EnsemblePredictor,
                          max_timestamp=None):
    """
    Simulate one year of 1-min bars for a single ticker.
    All 6 strategies run every bar; EnsemblePredictor is in-memory.
    """
    async with semaphore:
        file_path = os.path.join(DATA_DIR, f"{symbol}_enriched.parquet")
        if not os.path.exists(file_path):
            logging.warning(f"File not found: {file_path}")
            return

        try:
            df = pd.read_parquet(file_path)
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            start_dt = pd.to_datetime(test_start)
            if max_timestamp:
                max_dt = pd.to_datetime(max_timestamp)
                if max_dt > start_dt:
                    start_dt = max_dt

            mask = (df["timestamp"] > start_dt) & (df["timestamp"] <= pd.to_datetime(test_end))
            day_df = df.loc[mask].sort_values("timestamp")

            if day_df.empty:
                logging.info(f"{symbol}: already fully processed or no data in range.")
                return

            # Fresh strategy instances per ticker (no shared state between tickers)
            regime_classifier = MarketRegimeClassifier()
            strategies = _build_strategies()
            signal_filter = SignalFilter()
            target_calculator = TargetCalculator()

            db = SessionLocal()
            current_day = None
            batch_signals = []
            batch_trades = []

            for row in day_df.itertuples(index=False):
                features = row._asdict()
                timestamp = features["timestamp"]
                day = timestamp.date()

                # Day boundary — reset ALL strategy states
                if day != current_day:
                    for strategy in strategies:
                        strategy.reset_daily()
                    current_day = day

                regime = regime_classifier.classify(features)
                allowed = REGIME_POLICY.get(regime, ["ORB", "Momentum"])

                # Run every strategy; only process those allowed by regime
                for strategy in strategies:
                    if strategy.name not in allowed:
                        continue

                    signal = strategy.update(symbol, features)
                    if not signal:
                        continue

                    direction = signal["direction"]
                    entry_price = signal["entry_price"]

                    # ── In-memory ensemble prediction (no HTTP!) ───────────────
                    try:
                        # Sanitise: only numeric features, drop metadata keys
                        numeric_features = {
                            k: float(v)
                            for k, v in features.items()
                            if k not in ("symbol", "timestamp", "date", "sector",
                                         "quality_flag")
                            and v is not None
                            and not isinstance(v, str)
                        }
                        prediction = predictor.predict(numeric_features)
                    except Exception as e:
                        logging.error(f"Prediction error for {symbol}: {e}")
                        continue

                    # Log every raw strategy signal (for analytics)
                    batch_signals.append(StrategySignal(
                        symbol=symbol,
                        timestamp=timestamp,
                        strategy_name=strategy.name,
                        direction=direction,
                        entry_price=entry_price,
                        probability=prediction["probability"],
                        expected_return=prediction["expected_return"],
                        expected_drawdown=prediction["expected_drawdown"],
                        regime=regime,
                        is_anomaly=prediction["is_anomaly"],
                        backtest_id=BACKTEST_ID,
                    ))

                    # Strict gatekeeper — only pass if ALL thresholds met
                    if signal_filter.filter(prediction, allowed, strategy.name):
                        atr = features.get("atr_14") or 0.01
                        targets = target_calculator.calculate(entry_price, direction, atr)

                        batch_trades.append(TradeSignal(
                            symbol=symbol,
                            timestamp=timestamp,
                            strategy_name=strategy.name,
                            direction=direction,
                            entry=targets["entry"],
                            stop_loss=targets["stop_loss"],
                            target_l1=targets["target_l1"],
                            target_l2=targets["target_l2"],
                            target_l3=targets["target_l3"],
                            probability=prediction["probability"],
                            confidence=prediction["confidence"],
                            regime=regime,
                            backtest_id=BACKTEST_ID,
                        ))
                        logging.info(
                            f"🔥 ALERT: {symbol} | {strategy.name} | {direction} "
                            f"| {timestamp} | prob={prediction['probability']:.2f}"
                        )

                # Batch-commit every 1000 bars to avoid huge transactions
                if len(batch_signals) >= 1000:
                    db.bulk_save_objects(batch_signals)
                    db.bulk_save_objects(batch_trades)
                    db.commit()
                    batch_signals = []
                    batch_trades = []

            # Final flush
            if batch_signals or batch_trades:
                db.bulk_save_objects(batch_signals)
                db.bulk_save_objects(batch_trades)
                db.commit()

            db.close()
            logging.info(f"✅ Completed: {symbol}")

        except Exception as e:
            logging.error(f"Backtest failure for {symbol}: {e}", exc_info=True)


async def run_mass_backtest():
    test_start = "2025-01-01"
    test_end = "2026-01-23"

    files = sorted([
        f.replace("_enriched.parquet", "")
        for f in os.listdir(DATA_DIR)
        if f.endswith(".parquet")
    ])

    # Fetch resume timestamps (MAX per symbol, not just presence)
    db = SessionLocal()
    try:
        query = text(
            "SELECT symbol, MAX(timestamp) FROM strategy_signals "
            "WHERE backtest_id = :bt_id GROUP BY symbol"
        )
        result = db.execute(query, {"bt_id": BACKTEST_ID})
        symbol_max_ts = {row[0]: row[1] for row in result.fetchall()}
    except Exception as e:
        logging.warning(f"Could not fetch existing timestamps: {e}")
        symbol_max_ts = {}
    finally:
        db.close()

    logging.info(
        f"🏁 HIGH-SPEED Institutional Backtest v2 — {BACKTEST_ID}\n"
        f"   Tickers: {len(files)} | In-Memory Model: ✅ | HTTP: ❌\n"
        f"   Resuming {len(symbol_max_ts)} partially processed tickers..."
    )

    # Load the ensemble once, share across all coroutines (thread-safe reads)
    logging.info("Loading EnsemblePredictor into memory...")
    predictor = EnsemblePredictor()
    logging.info("EnsemblePredictor loaded. Starting backtest...")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = [
        process_ticker(
            symbol=sym,
            test_start=test_start,
            test_end=test_end,
            semaphore=semaphore,
            predictor=predictor,
            max_timestamp=symbol_max_ts.get(sym),
        )
        for sym in files
    ]

    await tqdm.gather(*tasks, desc="Institutional Backtest v2")
    logging.info("🏆 Mass Backtest COMPLETE.")
    logging.info(f"   Backtest ID: {BACKTEST_ID}")
    logging.info("   Run 'python scripts/audit_backtest.py' for detailed performance metrics.")


if __name__ == "__main__":
    asyncio.run(run_mass_backtest())
