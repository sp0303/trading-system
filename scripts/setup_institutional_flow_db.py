import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading:Trading%40123@localhost:5432/tradingsystem")

def setup_institutional_flow_db():
    engine = create_engine(DATABASE_URL)
    
    table_query = """
    CREATE TABLE IF NOT EXISTS institutional_flow (
        symbol VARCHAR(20) PRIMARY KEY,
        delivery_pct FLOAT,
        total_qty BIGINT,
        sentiment VARCHAR(50),
        score INT,
        reasoning TEXT[],
        last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    print("🚀 Setting up institutional_flow table...")
    with engine.connect() as conn:
        conn.execute(text(table_query))
        conn.commit()
    print("✅ Table institutional_flow is ready.")

if __name__ == "__main__":
    setup_institutional_flow_db()
