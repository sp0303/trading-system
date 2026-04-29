import os
import re
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DATA_PATH = os.getenv("DATA_PATH")

def clean_column_name(name):
    """Robust column name cleaning for PostgreSQL."""
    name = str(name).lower()
    # Replace non-alphanumeric characters with a single underscore
    name = re.sub(r'[^a-z0-9]+', '_', name)
    # Collapse multiple underscores and strip
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def initialize_schema():
    engine = create_engine(DATABASE_URL)
    
    # Load sample to get column names
    files = [f for f in os.listdir(DATA_PATH) if f.endswith('.parquet')]
    df = pd.read_parquet(os.path.join(DATA_PATH, files[0]))
    
    table_name = "ohlcv_enriched"
    
    # Drop existing table
    with engine.connect() as conn:
        print(f"Dropping existing table {table_name}...")
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE;"))
        conn.commit()

    # Define standard core columns
    sql_cols = ["id SERIAL PRIMARY KEY", "symbol VARCHAR(20) NOT NULL"]
    
    # Map Parquet columns to Clean DB columns
    for col_name, dtype in df.dtypes.items():
        clean_name = clean_column_name(col_name)
        
        if clean_name == 'timestamp':
            sql_cols.append(f"\"{clean_name}\" TIMESTAMP WITH TIME ZONE NOT NULL")
        else:
            sql_type = "DOUBLE PRECISION"
            if "int" in str(dtype):
                sql_type = "INTEGER"
            elif "object" in str(dtype):
                sql_type = "TEXT"
            # We use unquoted lowercase because they are now safe alphanumeric names
            sql_cols.append(f"{clean_name} {sql_type}")

    create_stmt = f"CREATE TABLE {table_name} (\n  " + ",\n  ".join(sql_cols) + "\n);"
    
    with engine.connect() as conn:
        print(f"Creating table {table_name} in database 'tradingsystem'...")
        conn.execute(text(create_stmt))
        print("Creating index on symbol and timestamp...")
        conn.execute(text(f"CREATE INDEX idx_symbol_ts ON {table_name} (symbol, timestamp);"))
        conn.commit()

    print("Database schema successfully created with safe column names.")

if __name__ == "__main__":
    initialize_schema()
