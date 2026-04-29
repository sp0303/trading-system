"""
Institutional PnL Truth-Auditor — v2
=====================================
Fixes vs v1:
  1. Models the REAL 40/40/20 partial close system (L1 → L2 → L3).
  2. Vectorized exit detection using cummin/cummax — no iterrows().
  3. Intraday 3:15 PM force-exit on any remaining open quantity.
  4. Detailed outcome breakdown: FULL_WIN / PARTIAL_WIN / STOP_LOSS / OPEN.
  5. Per-strategy breakdown in the report.
"""

import pandas as pd
import numpy as np
import os
import sqlalchemy as sa
from sqlalchemy import text
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DATA_DIR = "/home/sumanth/Desktop/trading-system/data/mode_ready_data/"
BACKTEST_ID = "BT_STABILIZED_FINAL_V1"    # Updated to match mass_backtest.py
SLIPPAGE = 0.0005              # 0.05% per side (entry + exit = 0.10% round-trip)

# Position sizing weights per level (must sum to 1.0)
L1_WEIGHT = 0.40
L2_WEIGHT = 0.40
L3_WEIGHT = 0.20

# Intraday cutoff: force-close any remaining position at 3:15 PM
INTRADAY_CUTOFF_MINUTE = 375  # minutes_from_open at 3:15 PM (225 min session end)


def _find_first_hit_timestamp(series: pd.Series, condition: pd.Series) -> pd.Timestamp:
    """Return timestamp of first True in condition, or NaT if never."""
    hits = series[condition]
    return hits.index[0] if len(hits) > 0 else pd.NaT


def audit_single_trade(signal: pd.Series, post_trade_df: pd.DataFrame) -> dict:
    """
    Given a single trade signal and the post-trade OHLCV bars, compute
    the blended PnL using the 40/40/20 partial close model.

    Returns a results dict with outcome, individual level PnLs, and net PnL.
    """
    entry = signal["entry"]
    sl = signal["stop_loss"]
    l1 = signal["target_l1"]
    l2 = signal["target_l2"]
    l3 = signal["target_l3"]
    direction = signal["direction"]
    trade_ts = pd.to_datetime(signal["timestamp"])
    strategy = signal.get("strategy_name", "UNKNOWN")

    if post_trade_df.empty:
        return {"outcome": "OPEN", "pnl": 0.0, "strategy": strategy}

    df = post_trade_df.copy()
    df = df.set_index("timestamp").sort_index()

    # ── Vectorized exit detection ──────────────────────────────────────────────
    if direction == "BUY":
        sl_hit_mask   = df["low"] <= sl
        l1_hit_mask   = df["high"] >= l1
        l2_hit_mask   = df["high"] >= l2
        l3_hit_mask   = df["high"] >= l3
        # Force-exit price at end of day = last available close
        force_exit_price = df["close"].iloc[-1] if not df.empty else entry
    else:  # SHORT
        sl_hit_mask   = df["high"] >= sl
        l1_hit_mask   = df["low"] <= l1
        l2_hit_mask   = df["low"] <= l2
        l3_hit_mask   = df["low"] <= l3
        force_exit_price = df["close"].iloc[-1] if not df.empty else entry

    sl_time = _find_first_hit_timestamp(df.index.to_series(), sl_hit_mask)
    l1_time = _find_first_hit_timestamp(df.index.to_series(), l1_hit_mask)
    l2_time = _find_first_hit_timestamp(df.index.to_series(), l2_hit_mask)
    l3_time = _find_first_hit_timestamp(df.index.to_series(), l3_hit_mask)

    # ── PnL calculation per exit level ────────────────────────────────────────
    def _pct(exit_price: float) -> float:
        if direction == "BUY":
            return (exit_price - entry) / entry
        else:
            return (entry - exit_price) / entry

    sl_pnl_pct = _pct(sl)
    l1_pnl_pct = _pct(l1)
    l2_pnl_pct = _pct(l2)
    l3_pnl_pct = _pct(l3)
    force_pnl_pct = _pct(force_exit_price)

    # ── Simulate position through the levels in time order ────────────────────
    # Remaining open weight
    remaining = 1.0
    blended_pnl = 0.0
    levels_hit = []

    # Check SL before L1
    sl_before_l1 = (
        pd.notna(sl_time) and
        (pd.isna(l1_time) or sl_time <= l1_time)
    )

    if sl_before_l1:
        # Full position stopped out
        blended_pnl = remaining * sl_pnl_pct
        outcome = "STOP_LOSS"
    else:
        # L1 hit first (or SL never hit)
        if pd.notna(l1_time):
            blended_pnl += L1_WEIGHT * l1_pnl_pct
            remaining -= L1_WEIGHT
            levels_hit.append("L1")

            # Check SL vs L2
            sl_before_l2 = (
                pd.notna(sl_time) and sl_time > l1_time and
                (pd.isna(l2_time) or sl_time <= l2_time)
            )
            if sl_before_l2:
                blended_pnl += remaining * sl_pnl_pct
                remaining = 0.0
                outcome = "SL_AFTER_L1"
            elif pd.notna(l2_time):
                blended_pnl += L2_WEIGHT * l2_pnl_pct
                remaining -= L2_WEIGHT
                levels_hit.append("L2")

                # Check SL vs L3
                sl_before_l3 = (
                    pd.notna(sl_time) and sl_time > l2_time and
                    (pd.isna(l3_time) or sl_time <= l3_time)
                )
                if sl_before_l3:
                    blended_pnl += remaining * sl_pnl_pct
                    remaining = 0.0
                    outcome = "SL_AFTER_L2"
                elif pd.notna(l3_time):
                    blended_pnl += L3_WEIGHT * l3_pnl_pct
                    remaining = 0.0
                    levels_hit.append("L3")
                    outcome = "FULL_WIN"
                else:
                    # L3 never hit — force exit remainder
                    blended_pnl += remaining * force_pnl_pct
                    remaining = 0.0
                    outcome = "PARTIAL_WIN_L2"
            else:
                # L2 never hit — force exit remainder
                blended_pnl += remaining * force_pnl_pct
                remaining = 0.0
                outcome = "PARTIAL_WIN_L1"
        else:
            # No level hit at all — force exit
            blended_pnl = force_pnl_pct
            outcome = "OPEN_FORCE_EXIT"

    # ── Apply round-trip slippage ──────────────────────────────────────────────
    net_pnl = blended_pnl - (SLIPPAGE * 2)

    return {
        "strategy": strategy,
        "outcome": outcome,
        "levels_hit": ",".join(levels_hit) if levels_hit else "none",
        "pnl_gross": round(blended_pnl * 100, 4),
        "pnl_net": round(net_pnl * 100, 4),
    }


def audit_pnl():
    """
    Pull all trade_signals for BACKTEST_ID from PostgreSQL.
    Cross-reference each with parquet price action.
    Report full blended PnL using 40/40/20 partial close model.
    """
    load_dotenv()
    engine = sa.create_engine(os.getenv("DATABASE_URL"))

    with engine.connect() as conn:
        query = text(
            "SELECT symbol, timestamp, direction, strategy_name, "
            "entry, stop_loss, target_l1, target_l2, target_l3 "
            "FROM trade_signals WHERE backtest_id = :bt_id"
        )
        signals_df = pd.read_sql(query, conn, params={"bt_id": BACKTEST_ID})

    if signals_df.empty:
        logging.warning(f"No trade signals found for {BACKTEST_ID}. Run mass_backtest.py first.")
        return

    logging.info(f"Auditing {len(signals_df)} trade signals for {BACKTEST_ID}...")
    results = []

    # Group by symbol to load each parquet file only once
    for symbol, group in signals_df.groupby("symbol"):
        file_path = os.path.join(DATA_DIR, f"{symbol}_enriched.parquet")
        if not os.path.exists(file_path):
            logging.warning(f"Parquet not found for {symbol}, skipping.")
            continue

        # Load price data for this symbol once
        price_df = pd.read_parquet(file_path, columns=["timestamp", "open", "high", "low", "close"])
        price_df["timestamp"] = pd.to_datetime(price_df["timestamp"])

        for _, signal in group.iterrows():
            trade_ts = pd.to_datetime(signal["timestamp"])
            # Post-trade bars: same day only (intraday rule)
            day_end = trade_ts.normalize() + pd.Timedelta(hours=15, minutes=15)
            post_trade = price_df[
                (price_df["timestamp"] > trade_ts) &
                (price_df["timestamp"] <= day_end)
            ].copy()

            result = audit_single_trade(signal, post_trade)
            result["symbol"] = symbol
            results.append(result)

    if not results:
        logging.warning("No results computed.")
        return

    res_df = pd.DataFrame(results)

    # ── Summary Report ─────────────────────────────────────────────────────────
    total = len(res_df)
    wins = (res_df["pnl_net"] > 0).sum()
    losses = (res_df["pnl_net"] < 0).sum()
    win_rate = wins / total * 100
    total_return = res_df["pnl_net"].sum()
    avg_win = res_df[res_df["pnl_net"] > 0]["pnl_net"].mean()
    avg_loss = res_df[res_df["pnl_net"] < 0]["pnl_net"].mean()

    print("\n" + "=" * 55)
    print(f"  📈 INSTITUTIONAL BACKTEST REPORT — {BACKTEST_ID}")
    print("=" * 55)
    print(f"  Total Trades  : {total}")
    print(f"  Wins          : {wins}  |  Losses: {losses}")
    print(f"  Win Rate      : {win_rate:.2f}%")
    print(f"  Avg Win       : {avg_win:.4f}%  |  Avg Loss: {avg_loss:.4f}%")
    print(f"  Total Return  : {total_return:.4f}% (net of 0.05% slippage/side)")
    print("-" * 55)

    print("\n  📊 OUTCOME BREAKDOWN:")
    for outcome, count in res_df["outcome"].value_counts().items():
        pct = count / total * 100
        avg_pnl = res_df[res_df["outcome"] == outcome]["pnl_net"].mean()
        print(f"    {outcome:<22} {count:>5} ({pct:.1f}%)  avg={avg_pnl:.4f}%")

    print("\n  📊 PER-STRATEGY BREAKDOWN:")
    strategy_summary = res_df.groupby("strategy").agg(
        trades=("pnl_net", "count"),
        win_rate=("pnl_net", lambda x: (x > 0).mean() * 100),
        avg_pnl=("pnl_net", "mean"),
        total_pnl=("pnl_net", "sum"),
    ).round(3)
    print(strategy_summary.to_string())
    print("=" * 55 + "\n")


if __name__ == "__main__":
    audit_pnl()
