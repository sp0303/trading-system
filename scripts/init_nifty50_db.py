import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_DIR = "/home/sumanth/Desktop/trading-system/data/enriched_data_v2_nifty50"

def clean_column_name(name):
    """Robust column name cleaning matching the ingestion script."""
    name = str(name).lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def initialize_nifty50_schema():
    engine = create_engine(DATABASE_URL)
    
    # Use any sample file from NIFTY50 folder to define the schema
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('_enriched.parquet')]
    sample_file = os.path.join(DATA_DIR, files[0])
    
    print(f"Initializing schema based on {sample_file}...")
    df = pd.read_parquet(sample_file)
    df['symbol'] = "INIT"
    df['timestamp'] = pd.to_datetime(df['timestamp']) # Fix timestamp before defining schema
    df.columns = [clean_column_name(c) for c in df.columns]
    
    # 1. Clean Slate: Drop existing table
    with engine.connect() as conn:
        print("Dropping existing table ohlcv_enriched...")
        conn.execute(text("DROP TABLE IF EXISTS ohlcv_enriched CASCADE;"))
        conn.commit()
    
    # 2. Use Pandas to create the base table with correct types
    # Fix: We'll create the table using if_exists='replace' but with 0 rows
    df.head(0).to_sql("ohlcv_enriched", engine, if_exists="replace", index=False)
    
    # 3. Post-Ingest structure (PK and indices)
    with engine.connect() as conn:
        print("Adding SERIAL primary key and indexing symbol + timestamp...")
        conn.execute(text("ALTER TABLE ohlcv_enriched ADD COLUMN id SERIAL PRIMARY KEY;"))
        conn.execute(text("CREATE INDEX idx_symbol_ts ON ohlcv_enriched (symbol, timestamp);"))
        conn.commit()

    print("NIFTY50 database schema initialized successfully.")

if __name__ == "__main__":
    initialize_nifty50_schema()
