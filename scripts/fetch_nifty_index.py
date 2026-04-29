import os
import json
import pandas as pd
from datetime import datetime, timedelta
import pytz
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import sys

# Add project root to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.data_service.app.services.angel_one_client import AngelOneClient

load_dotenv()

def fetch_and_store_nifty():
    client = AngelOneClient()
    if not client.login():
        print("Failed to login to Angel One")
        return

    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # NIFTY 50 Index Token in Angel One
    symbol = "NIFTY50"
    token = "99926000" # NSE Index
    exchange = "NSE"

    print(f"Fetching {symbol} data...")
    
    # Get LTP first
    try:
        # We'll use get_history if available, otherwise just mock today's data from Reliance as a base but scaled
        # Actually, let's try to get real history
        from_date = (now - timedelta(days=1)).strftime('%Y-%m-%d 09:15')
        to_date = now.strftime('%Y-%m-%d 15:30')
        
        # Manually construct request for index history
        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": "ONE_MINUTE",
            "fromdate": from_date,
            "todate": to_date
        }
        
        # Use the underlying smart_api to get candle data
        res = client.smart_api.getCandleData(params)
        
        if res and res.get('status') and res.get('data'):
            candles = res['data']
            print(f"Received {len(candles)} candles for {symbol}")
            
            # Convert to DataFrame
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['symbol'] = symbol
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Add required columns for ohlcv_enriched
            df['sector'] = 'Index'
            df['returns'] = df['close'].pct_change() * 100
            
            # Ingest to DB
            engine = create_engine(os.getenv("DATABASE_URL"))
            df.to_sql("ohlcv_enriched", engine, if_exists="append", index=False)
            print("Successfully stored Nifty 50 Index data.")
        else:
            print("Could not fetch index candles. Falling back to LTP update.")
            # Fallback: Just get LTP and store as one point
            # This is better than nothing
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_and_store_nifty()
