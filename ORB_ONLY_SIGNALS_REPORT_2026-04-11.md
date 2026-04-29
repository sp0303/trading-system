# ORB-Only Signals Report

Date: 2026-04-11

## Question

Why are only ORB signals showing up?

## Short Answer

It is not because only ORB exists or only ORB can trigger.

The other strategies do trigger on the data, but almost all of them are getting blocked before they become final alerts.

## What Was Checked

### 1. Strategy logs

I checked the signal and backtest logs for:

- ORB
- VWAP Reversion
- Momentum
- Relative Strength
- Vol Squeeze
- Volume Reversal
- filter pass/fail logs

Observed:

- ORB trigger logs appear heavily.
- ORB filter-pass logs appear heavily.
- comparable non-ORB pass logs were not found in the backtest logs checked.

### 2. Raw strategy-condition presence in parquet data

I scanned the local parquet feature store and checked whether non-ORB setup conditions exist at all.

The conditions do exist in meaningful numbers.

Sample findings from the data scan:

- `Momentum_LONG`: 189031
- `Momentum_SHORT`: 202720
- `VWAP_LONG`: 145301
- `VWAP_SHORT`: 126729
- `RS_LONG`: 89422
- `VolRev_LONG`: 4541
- `VolRev_SHORT`: 5275

This proves the non-ORB setups are present in the data.

### 3. Strategy replay on local parquet files

I replayed the strategy logic on a sample of parquet files with current regime policy.

Observed raw trigger counts:

- `Momentum`: 1422
- `VWAP Reversion`: 1303
- `ORB`: 1288
- `Relative Strength`: 1224
- `Volume Reversal`: 353

This proves non-ORB strategies are firing at the strategy layer.

## Main Conclusion

The pipeline is behaving like this:

1. strategy triggers
2. model predicts
3. signal filter checks probability / MFE / MAE
4. only ORB consistently survives to final alert

So the real issue is:

- not strategy existence
- not strategy triggering
- mainly model/filter behavior after trigger

## Root Causes

## 1. Primary Cause: label/model/filter mismatch

This matches the previously identified MAE-label issue.

Current situation:

- `target_mae` labels are too extreme
- model learns very high expected drawdown
- strict `mae_threshold=1.0` blocks most trades
- ORB is the only strategy still getting predictions strong enough to pass more often

This is the biggest reason for ORB-only final alerts.

## 2. Secondary Cause: VWAP unit mismatch

There is a likely logic bug in the VWAP strategy path.

In:

- [shared/feature_engineer.py](/home/sumanth/Desktop/trading-system/shared/feature_engineer.py:80)

`distance_from_vwap` is stored as a percentage.

In:

- [services/signal-service/app/strategies/vwap_reversion.py](/home/sumanth/Desktop/trading-system/services/signal-service/app/strategies/vwap_reversion.py:42)

that distance is compared against `1.5 * atr`, where ATR is an absolute price value.

That mixes:

- percent distance
- absolute ATR

This mismatch can suppress valid VWAP entries heavily.

## 3. Tertiary Cause: Vol Squeeze appears too restrictive

Vol Squeeze requires:

- 3 squeeze bars first
- then breakout bar
- plus regime allowance

In sampled replay, actual `Vol Squeeze` triggers did not show up.

So for that strategy, the issue is likely strict trigger design in addition to later filtering.

## 4. Regime policy is not the main blocker

The regime policy does block some strategies depending on market condition, but it is not the main reason for ORB-only alerts.

Reason:

- replay counts already show that Momentum, VWAP Reversion, Relative Strength, and Volume Reversal can still trigger under current regime rules

## Evidence Summary

### Non-ORB strategies do exist

Confirmed.

### Non-ORB strategies do trigger

Confirmed.

### Only ORB is consistently passing the final filter

Confirmed from logs checked.

### Therefore the problem is downstream of trigger generation

Confirmed.

## Final Diagnosis

Why only ORB signals are coming:

- ORB is not the only strategy firing.
- ORB is the only strategy consistently passing the current model + filter combination.
- Main cause: unrealistic MAE labels causing non-ORB predictions to look too risky.
- Secondary cause: likely VWAP strategy unit mismatch.
- Additional cause: Vol Squeeze trigger path is very restrictive.

## Recommended Fix Order

1. Fix the target engineering / label realism and retrain.
2. Fix the VWAP unit mismatch.
3. Re-check strategy-wise filter-pass counts after retraining.
4. If Vol Squeeze is still zero, inspect its trigger design separately.

## Status

Saved for later work. No code changes made as part of this report.
