import os
import sys
import logging
import pytz
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from tqdm import tqdm

# Add project root to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.data_service.app.services.angel_one_client import AngelOneClient
from shared.feature_engineer import FeatureEngineer

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
IST = pytz.timezone('Asia/Kolkata')

class DataSyncOrchestrator:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.client = AngelOneClient()
        self.engineer = FeatureEngineer()
        
    def get_active_symbols(self):
        """Fetches distinct symbols from the database."""
        with self.engine.connect() as conn:
            query = text("SELECT DISTINCT symbol FROM ohlcv_enriched")
            result = conn.execute(query)
            return [row[0] for row in result]

    def get_last_timestamp(self, symbol):
        """Gets the latest timestamp for a symbol."""
        with self.engine.connect() as conn:
            query = text("SELECT MAX(timestamp) FROM ohlcv_enriched WHERE symbol = :symbol")
            result = conn.execute(query, {"symbol": symbol}).scalar()
            if result and result.tzinfo is None:
                # If naive, assume it's IST as per our logic
                result = IST.localize(result)
            return result

    def sync_all(self, target_symbol=None, force=False):
        """Orchestrates the sync for all symbols or a specific one."""
        if not self.client.login():
            logging.error("Failed to connect to Angel One. Sync aborted.")
            return

        if target_symbol:
            symbols = [target_symbol]
        else:
            symbols = self.get_active_symbols()
            
        logging.info(f"Starting sync for {len(symbols)} symbols (Force={force})...")

        # 1. Sync Index Data first (NIFTY and BANKNIFTY)
        nifty_df = self._fetch_index_data("NIFTYBEES", "NSE")
        banknifty_df = self._fetch_index_data("BANKBEES", "NSE")

        # 2. Sync Stock Data
        for symbol in tqdm(symbols, desc="Syncing Symbols"):
            try:
                self.sync_symbol(symbol, nifty_df, banknifty_df, force=force)
            except Exception as e:
                logging.error(f"Error syncing {symbol}: {e}")

    def _fetch_index_data(self, symbol, exchange):
        """Helper to fetch 1-min index proxy data for the last few days."""
        now = datetime.now(IST)
        to_date = now.strftime("%Y-%m-%d %H:%M")
        from_date = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
        
        df = self.client.fetch_historical_data(symbol, from_date, to_date, exchange=exchange)
        if df is not None:
            # Standardize column names for merge
            df = df.rename(columns={'timestamp': 'timestamp'})
            return df
        return None

    def sync_symbol(self, symbol, nifty_df, banknifty_df, force=False):
        """Syncs a single symbol from its last record to now."""
        last_ts = self.get_last_timestamp(symbol)
        
        if last_ts is None:
            # If no data, start from 2025-01-01
            start_dt = IST.localize(datetime(2025, 1, 1, 9, 15))
        else:
            # Start from last_ts + 1 minute
            start_dt = last_ts + timedelta(minutes=1)
            
        now = datetime.now(IST)
        
        # 🔹 INTELLIGENT SYNC THRESHOLD
        # If the last data point is within 2 minutes of NOW, we assume the WebSocket 
        # is healthy and live. Calling the API for 1 or 2 candles is redundant.
        if not force and last_ts and (now - last_ts) < timedelta(minutes=2):
            logging.info(f"⏭️ Skipping {symbol}: Already up-to-date via Live WebSocket (last data: {last_ts.strftime('%H:%M:%S')})")
            return

        # Don't sync if last_ts is today's closing or later
        if start_dt > now:
            logging.debug(f"Symbol {symbol} is already up to date.")
            return

        from_date = start_dt.strftime("%Y-%m-%d %H:%M")
        to_date = now.strftime("%Y-%m-%d %H:%M")

        # Fetch Raw Data
        logging.info(f"📡 Fetching historical gap for {symbol}: {from_date} to {to_date}")
        raw_df = self.client.fetch_historical_data(symbol, from_date, to_date)
        
        if raw_df is None or raw_df.empty:
            logging.debug(f"No new data for {symbol} since {from_date}")
            return
        
        # Ensure 'timestamp' in raw_df is IST aware for downstream merge if needed
        if raw_df['timestamp'].dt.tz is None:
            raw_df['timestamp'] = raw_df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(IST)
        else:
            raw_df['timestamp'] = raw_df['timestamp'].dt.tz_convert(IST)

        # Enrich Data
        enriched_df = self.engineer.enrich_data(raw_df, symbol, nifty_df, banknifty_df)
        
        # Save to DB
        self._save_to_db(enriched_df)
        logging.info(f"Synced {len(enriched_df)} records for {symbol}")

    def _save_to_db(self, df):
        """Appends enriched data to ohlcv_enriched table."""
        # Convert all double precision fields to float for DB compatibility
        # Ensure 'symbol' is last or matches schema order if needed
        # We'll use the SQLAlchemy to_sql as it's easier
        
        # Clean columns to match DB (lowercase)
        df.columns = [c.lower() for c in df.columns]
        
        # Select only columns present in the DB schema (to avoid errors with 'date' etc.)
        # I'll use the list from the schema query
        db_cols = [
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'prev_close', 'returns', 'log_return', 'range', 'range_pct',
            'cum_vol', 'vwap', 'rolling_avg_volume', 'is_volume_spike',
            'vol_5', 'vol_15', 'distance_from_vwap', 'day_open', 
            'distance_from_open', 'volume_zscore', 'volume_spike_ratio',
            'minutes_from_open', 'minutes_to_close', 'day_of_week',
            'is_monday', 'is_friday', 'is_expiry_day', 'rsi_14', 
            'macd_hist', 'adx_14', 'stoch_k_14', 'atr_14', 'bollinger_b',
            'volatility_20d', 'obv_slope_10', 'cmf_20', 'rvol_20',
            'return_lag_1', 'return_lag_2', 'return_5d', 'rsi_lag_1',
            'macd_hist_lag_1', 'atr_lag_1', 'sin_dayofweek', 'cos_dayofweek',
            'frac_diff_close', 'wavelet_return', 'symbol'
        ]
        
        # Filter columns
        final_df = df[[c for c in db_cols if c in df.columns]]
        
        # Append to DB
        final_df.to_sql("ohlcv_enriched", self.engine, if_exists="append", index=False)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, help="Specific symbol to sync")
    parser.add_argument("--force", action="store_true", help="Force sync ignoring threshold")
    args = parser.parse_args()
    
    orchestrator = DataSyncOrchestrator()
    orchestrator.sync_all(target_symbol=args.symbol, force=args.force)
