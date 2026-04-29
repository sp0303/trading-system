import os
import json
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
cache_dir = "services/fundamental-service/cache"

def migrate():
    count = 0
    with engine.connect() as conn:
        for f in os.listdir(cache_dir):
            if f.endswith(".json"):
                path = os.path.join(cache_dir, f)
                with open(path, "r") as json_file:
                    data = json.load(json_file)
                
                query = text("""
                    INSERT INTO institutional_fundamentals (
                        symbol, market_cap, pe_ratio, pb_ratio, dividend_yield, 
                        high_52w, low_52w, debt_to_equity, return_on_equity, 
                        sector, long_summary, last_updated
                    ) VALUES (
                        :symbol, :market_cap, :pe_ratio, :pb_ratio, :dividend_yield,
                        :high_52w, :low_52w, :debt_to_equity, :return_on_equity,
                        :sector, :long_summary, CURRENT_TIMESTAMP
                    ) ON CONFLICT (symbol) DO UPDATE SET last_updated = CURRENT_TIMESTAMP;
                """)
                conn.execute(query, data)
                count += 1
        conn.commit()
    print(f"Migrated {count} symbols to DB.")

if __name__ == "__main__":
    migrate()
