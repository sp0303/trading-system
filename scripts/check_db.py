import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def check_db():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Check Account
        acc = conn.execute(text("SELECT * FROM paper_accounts WHERE id = 1")).fetchone()
        print(f"Account: {dict(acc._mapping) if acc else 'MISSING'}")
        
        # Check Positions
        pos_count = conn.execute(text("SELECT count(*) FROM paper_positions")).scalar()
        print(f"Position Count: {pos_count}")
        
        # Check Symbols
        sym_count = conn.execute(text("SELECT count(DISTINCT symbol) FROM ohlcv_enriched")).scalar()
        print(f"Symbol Count (ohlcv_enriched): {sym_count}")
        
        # Check Signals
        try:
            sig_count = conn.execute(text("SELECT count(*) FROM trade_signals")).scalar()
            print(f"Signal Count: {sig_count}")
        except Exception as e:
            print(f"Signal table check failed: {e}")
        
        # Sample Symbol
        if sym_count > 0:
            sample = conn.execute(text("SELECT symbol FROM symbols LIMIT 1")).scalar()
            print(f"Sample Symbol: {sample}")

if __name__ == "__main__":
    check_db()
