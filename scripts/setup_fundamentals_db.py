import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

query = """
CREATE TABLE IF NOT EXISTS institutional_fundamentals (
    symbol VARCHAR(20) PRIMARY KEY,
    market_cap DOUBLE PRECISION,
    pe_ratio DOUBLE PRECISION,
    pb_ratio DOUBLE PRECISION,
    dividend_yield DOUBLE PRECISION,
    high_52w DOUBLE PRECISION,
    low_52w DOUBLE PRECISION,
    debt_to_equity DOUBLE PRECISION,
    return_on_equity DOUBLE PRECISION,
    sector VARCHAR(100),
    long_summary TEXT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

try:
    with engine.connect() as conn:
        conn.execute(text(query))
        conn.commit()
    print("Table institutional_fundamentals created/verified successfully.")
except Exception as e:
    print(f"Error: {e}")
