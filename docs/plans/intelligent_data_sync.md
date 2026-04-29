# Implementation Plan - Intelligent Data Sync (WebSocket Prioritization)

## Goal
Optimize the data pipeline to rely on real-time WebSocket data and use the REST API only for bridging gaps (e.g., overnight or during downtime).

## Proposed Changes

### 1. Data Sync Script (`scripts/sync_data.py`)
- **Smart Check**: Before calling the `AngelOneClient.fetch_historical_data` method, the script will query the local `ohlcv_enriched` table.
- **Decision Logic**: 
    - If the database already has data for the requested timeframe, skip the API call.
    - If there is a gap (e.g., system was off from 9:15 to 10:00), fetch ONLY the missing 45 minutes.
- **Rate Limit Protection**: By skipping redundant live-syncing, we preserve API usage for actual historical research.

### 2. API Gateway (`gateway/main.py`)
- **Dashboard Optimization**: Direct the dashboard to pull "Technical Snapshots" from the local PostgreSQL database (filled by WebSocket + Bar Aggregators) instead of triggering a manual `/sync` command.

## Verification
- Monitor `logs/sync.log` to confirm the message: `"Historical data exists locally. Skipping API call for SYMBOL."`
- Verify that live candles appear on the dashboard without manual intervention.

---
**Scheduled for: Tomorrow**
