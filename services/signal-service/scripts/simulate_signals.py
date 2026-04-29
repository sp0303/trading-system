import pandas as pd
import httpx
import os
import asyncio
from tqdm import tqdm
import logging
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SIGNAL_SERVICE_URL = "http://localhost:7004/process"
RESET_DAY_URL = "http://localhost:7004/reset_day"
DATA_DIR = "/home/sumanth/Desktop/trading-system/data/mode_ready_data/"

async def simulate_stock(symbol: str, test_date: str):
    """
    Simulates a full trading day for a single symbol at 1-minute resolution.
    """
    file_path = os.path.join(DATA_DIR, f"{symbol}_enriched.parquet")
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return

    df = pd.read_parquet(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Filter for the target test day
    day_df = df[df['timestamp'].dt.date == pd.to_datetime(test_date).date()]
    if day_df.empty:
        logging.info(f"No data for {symbol} on {test_date}")
        return

    logging.info(f"🚀 Simulating {len(day_df)} minutes for {symbol} on {test_date}...")

    # Sort to ensure sequential simulation
    day_df = day_df.sort_values('timestamp')

    async with httpx.AsyncClient() as client:
        reset_response = await client.post(RESET_DAY_URL, timeout=20.0)
        reset_response.raise_for_status()

        for _, row in tqdm(day_df.iterrows(), total=len(day_df), desc=f"{symbol}"):
            payload = {
                "symbol": symbol,
                "timestamp": row['timestamp'].isoformat(),
                "features": row.to_dict()
            }
            
            # Clean dataframe row for JSON serialization
            clean_features = {}
            for k, v in row.to_dict().items():
                if k == 'timestamp':
                    continue
                # Handle numpy types
                if hasattr(v, 'item'):
                    val = v.item()
                else:
                    val = v
                
                # Handle date/datetime objects (Hedge Fund Grade sanitization)
                if isinstance(val, (datetime, pd.Timestamp)):
                    clean_features[k] = val.isoformat()
                elif hasattr(val, 'isoformat'): # Catch-all for date-like objects
                    clean_features[k] = val.isoformat()
                else:
                    clean_features[k] = val
                    
            payload["features"] = clean_features
            
            try:
                response = await client.post(SIGNAL_SERVICE_URL, json=payload, timeout=20.0)
                result = response.json()

                if result.get("status") == "signals_generated":
                    logging.info(
                        f"🔥 Signals Detected: {symbol} at {payload['timestamp']} -> {result.get('alerts', [])}"
                    )
            except Exception as e:
                logging.error(f"Failed to process minute: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Institutional Signal Service Simulation")
    parser.add_argument("--symbol", type=str, default="RELIANCE", help="Stock symbol to simulate")
    parser.add_argument("--date", type=str, default="2026-01-05", help="Date to simulate (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    asyncio.run(simulate_stock(args.symbol, args.date))
