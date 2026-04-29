import os
import re
import pandas as pd
import pytz
from sqlalchemy import create_engine
from tqdm import tqdm
from dotenv import load_dotenv
import shutil

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_DIR = "/home/sumanth/Desktop/trading-system/data/enriched_data_v2_nifty50"
START_DATE = "2025-01-01"

def clean_column_name(name):
    """Robust column name cleaning for PostgreSQL."""
    name = str(name).lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def check_disk_space(path, min_gb=5):
    """Check if there is enough disk space."""
    total, used, free = shutil.disk_usage(path)
    free_gb = free // (2**30)
    if free_gb < min_gb:
        print(f"⚠️ Warning: Low disk space ({free_gb} GB free). Minimum {min_gb} GB recommended.")
        return False
    return True

def process_and_ingest_file(file_name, engine):
    """Process a single file and ingest filtered data into Postgres."""
    file_path = os.path.join(DATA_DIR, file_name)
    symbol = file_name.replace("_enriched.parquet", "").replace(".parquet", "")
    
    try:
        # 1. Read Parquet
        df = pd.read_parquet(file_path)
        
        # 2. Convert and Filter by Date
        if 'timestamp' not in df.columns:
            return f"Error: No timestamp in {symbol}"
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter for 2025 onwards
        df = df[df['timestamp'] >= START_DATE]
        
        if df.empty:
            return f"Skipped {symbol}: No data after {START_DATE}"
            
        # 3. Standardize column names and add symbol
        df['symbol'] = symbol
        df.columns = [clean_column_name(c) for c in df.columns]
        
        # 4. Ingest to Postgres in chunks
        chunk_size = 5000
        total_rows = len(df)
        
        for i in range(0, total_rows, chunk_size):
            chunk = df.iloc[i : i + chunk_size]
            chunk.to_sql(
                "ohlcv_enriched", 
                engine, 
                if_exists="append", 
                index=False,
                method="multi"
            )
        
        return f"Successfully ingested {symbol} ({total_rows} rows)"
        
    except Exception as e:
        return f"Error ingesting {symbol}: {e}"

def main():
    if not check_disk_space("/home/sumanth"):
        return

    # 1. Create Engine
    engine = create_engine(DATABASE_URL)

    # 2. Get all files in directory
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.parquet')]
    print(f"Starting ingestion for {len(files)} files from {START_DATE} onwards...")

    # We process sequentially to avoid overwhelming the DB
    for file_name in tqdm(files, desc="Overall Progress"):
        res = process_and_ingest_file(file_name, engine)
        if "Error" in res or "Warning" in res:
            print(f"\n{res}")
        # else:
        #    print(f"\n{res}")
    
    print("\nIngestion Complete.")

if __name__ == "__main__":
    main()
