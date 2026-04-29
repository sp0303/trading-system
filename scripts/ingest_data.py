import os
import pandas as pd
import pytz
from sqlalchemy import create_engine
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_PATH = os.getenv("DATA_PATH")
IST = pytz.timezone("Asia/Kolkata")

def convert_to_ist(df):
    """Ensure timestamp is in IST."""
    if 'timestamp' in df.columns:
        # If timestamp is already timezone-aware, convert to IST
        # If naive, assume it's UTC and convert to IST
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(IST)
        else:
            df['timestamp'] = df['timestamp'].dt.tz_convert(IST)
    return df

def ingest_all_files():
    engine = create_engine(DATABASE_URL)
    
    # Get all parquet files
    files = [f for f in os.listdir(DATA_PATH) if f.endswith('_enriched.parquet')]
    print(f"Found {len(files)} files to ingest.")
    
    for file_name in tqdm(files, desc="Ingesting Data"):
        symbol = file_name.replace("_enriched.parquet", "")
        file_path = os.path.join(DATA_PATH, file_name)
        
        try:
            # Read Parquet
            df = pd.read_parquet(file_path)
            
            # Pre-process
            df['symbol'] = symbol
            df = convert_to_ist(df)
            
            # Reorder columns to match DB (symbol and timestamp first)
            cols = ['symbol'] + [c for c in df.columns if c != 'symbol']
            df = df[cols]
            
            # Ingest to Postgres
            df.to_sql(
                "ohlcv_enriched", 
                engine, 
                if_exists="append", 
                index=False, 
                chunksize=10000, 
                method="multi"
            )
            
        except Exception as e:
            print(f"Error ingesting {symbol}: {e}")

if __name__ == "__main__":
    print("Starting data ingestion (Strict IST Timing)...")
    ingest_all_files()
    print("Ingestion complete.")
