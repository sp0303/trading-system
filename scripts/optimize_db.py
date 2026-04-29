import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def optimize_db():
    engine = create_engine(os.getenv('DATABASE_URL'))
    
    with engine.connect() as conn:
        print("Checking indexes for 'ohlcv_enriched'...")
        res = conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'ohlcv_enriched';"))
        indexes = [r[0] for r in res.fetchall()]
        print(f"Existing indexes: {indexes}")
        
        # Check for symbol + timestamp index
        target_idx = "idx_ohlcv_symbol_timestamp"
        if target_idx not in indexes:
            print(f"Adding index {target_idx} for faster lookups...")
            conn.execute(text(f"CREATE INDEX {target_idx} ON ohlcv_enriched (symbol, timestamp DESC);"))
            conn.commit()
            print("Index added successfully ✅")
        else:
            print("Optimal index already exists ✅")
            
        # Also check for symbol index for the watchlist
        sym_idx = "idx_ohlcv_symbol"
        if sym_idx not in indexes:
            print(f"Adding index {sym_idx}...")
            conn.execute(text(f"CREATE INDEX {sym_idx} ON ohlcv_enriched (symbol);"))
            conn.commit()
            print("Symbol index added successfully ✅")

if __name__ == "__main__":
    optimize_db()
