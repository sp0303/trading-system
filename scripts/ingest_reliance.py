import os
import re
import pandas as pd
import pytz
from sqlalchemy import create_engine, text
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_PATH = os.getenv("DATA_PATH")
IST = pytz.timezone("Asia/Kolkata")

def convert_to_ist(df):
    """Ensure timestamp is in IST."""
    if 'timestamp' in df.columns:
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(IST)
        else:
            df['timestamp'] = df['timestamp'].dt.tz_convert(IST)
    return df

def clean_column_name(name):
    """Robust column name cleaning."""
    name = str(name).lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def ingest_reliance_robust():
    engine = create_engine(DATABASE_URL)
    
    file_name = "RELIANCE_enriched.parquet"
    file_path = os.path.join(DATA_PATH, file_name)
    
    try:
        print(f"Reading {file_name} for ROBUST ingestion...")
        df = pd.read_parquet(file_path)
        
        # 1. Pre-process
        df['symbol'] = "RELIANCE"
        df = convert_to_ist(df)
        df.columns = [clean_column_name(c) for c in df.columns]
        
        # 2. Table Creation (Replace with empty structure first)
        print(f"Creating table with {len(df.columns)} columns...")
        df.head(0).to_sql("ohlcv_enriched", engine, if_exists="replace", index=False)
        
        # 3. Batch Ingestion with Progress Bar
        chunk_size = 2000
        num_chunks = (len(df) // chunk_size) + 1
        
        print(f"Ingesting {len(df)} rows in {num_chunks} chunks...")
        for i in tqdm(range(0, len(df), chunk_size), desc="Ingesting"):
            chunk = df.iloc[i : i + chunk_size]
            chunk.to_sql(
                "ohlcv_enriched", 
                engine, 
                if_exists="append", 
                index=False,
                method="multi"
            )
            
        # 4. Post-Ingest: Add ID and Indices
        with engine.connect() as conn:
            print("\nFinalizing: Adding Primary Key and Indices...")
            conn.execute(text("ALTER TABLE ohlcv_enriched ADD COLUMN id SERIAL PRIMARY KEY;"))
            conn.execute(text("CREATE INDEX idx_symbol_ts ON ohlcv_enriched (symbol, timestamp);"))
            conn.commit()
            
        print(f"SUCCESS! RELIANCE data loaded and indexed.")
        
        # 5. Final Verification
        with engine.connect() as conn:
            res = conn.execute(text("SELECT count(*) FROM ohlcv_enriched WHERE symbol='RELIANCE'")).scalar()
            print(f"Total rows in DB for RELIANCE: {res}")
            
            print("\nSample (Last 3 records IST):")
            res_rows = conn.execute(text("SELECT timestamp, open, close FROM ohlcv_enriched ORDER BY timestamp DESC LIMIT 3"))
            for r in res_rows:
                print(f"TS: {r[0]}, Open: {r[1]}, Close: {r[2]}")
                
    except Exception as e:
        print(f"\n[ERROR] Ingestion Failed: {e}")

if __name__ == "__main__":
    ingest_reliance_robust()
