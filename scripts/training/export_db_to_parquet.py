import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from tqdm import tqdm
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
OUTPUT_DIR = "data/mode_ready_data"

def export_db_to_parquet():
    """
    Exports ohlcv_enriched table from PostgreSQL to symbol-based parquet files.
    Ensures data is ready for the EnsembleTrainer.
    """
    engine = create_engine(DATABASE_URL)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with engine.connect() as conn:
        # Get list of symbols
        symbols = [row[0] for row in conn.execute(text("SELECT DISTINCT symbol FROM ohlcv_enriched"))]
        logging.info(f"Found {len(symbols)} symbols in database.")
        
        for symbol in tqdm(symbols, desc="Exporting to Parquet"):
            try:
                # Query all data for the symbol
                query = text("SELECT * FROM ohlcv_enriched WHERE symbol = :symbol ORDER BY timestamp")
                df = pd.read_sql(query, conn, params={"symbol": symbol})
                
                if df.empty:
                    continue
                
                # The EnsembleTrainer expects these specific targets (if available)
                # target_prob, target_mfe, target_mae
                # If they don't exist in DB, we'll calculate dummy or placeholder values for now
                # though usually they are calculated by a separate labeling script.
                
                filename = os.path.join(OUTPUT_DIR, f"{symbol}_enriched.parquet")
                df.to_parquet(filename, index=False)
            except Exception as e:
                logging.error(f"Error exporting {symbol}: {e}")

if __name__ == "__main__":
    export_db_to_parquet()
    logging.info(f"Export complete. Files saved to {OUTPUT_DIR}")
