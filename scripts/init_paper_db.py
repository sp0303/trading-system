import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def init_paper_tables():
    engine = create_engine(DATABASE_URL)
    
    commands = [
        # 1. paper_orders
        """
        CREATE TABLE IF NOT EXISTS paper_orders (
          id SERIAL PRIMARY KEY,
          client_order_id VARCHAR(100) UNIQUE NOT NULL,
          trade_signal_id INTEGER NULL,
          parent_client_order_id VARCHAR(100) NULL,
          symbol VARCHAR(30) NOT NULL,
          side VARCHAR(10) NOT NULL,
          qty INTEGER NOT NULL,
          requested_price DOUBLE PRECISION NULL,
          filled_qty INTEGER NOT NULL DEFAULT 0,
          avg_fill_price DOUBLE PRECISION NULL,
          order_type VARCHAR(20) NOT NULL DEFAULT 'MARKET',
          strategy_name VARCHAR(100) NULL,
          regime VARCHAR(50) NULL,
          source VARCHAR(30) NOT NULL DEFAULT 'frontend',
          status VARCHAR(30) NOT NULL,
          note TEXT NULL,
          extra JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
          updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """,
        # 2. paper_order_audit
        """
        CREATE TABLE IF NOT EXISTS paper_order_audit (
          id SERIAL PRIMARY KEY,
          client_order_id VARCHAR(100) NOT NULL,
          from_status VARCHAR(30) NULL,
          to_status VARCHAR(30) NOT NULL,
          note TEXT NULL,
          meta JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """,
        # 3. paper_fills
        """
        CREATE TABLE IF NOT EXISTS paper_fills (
          id SERIAL PRIMARY KEY,
          client_order_id VARCHAR(100) NOT NULL,
          symbol VARCHAR(30) NOT NULL,
          side VARCHAR(10) NOT NULL,
          qty INTEGER NOT NULL,
          price DOUBLE PRECISION NOT NULL,
          fees DOUBLE PRECISION NOT NULL DEFAULT 0,
          slippage_bps DOUBLE PRECISION NOT NULL DEFAULT 0,
          venue VARCHAR(20) NOT NULL DEFAULT 'PAPER',
          extra JSONB NOT NULL DEFAULT '{}'::jsonb,
          timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """,
        # 4. paper_positions
        """
        CREATE TABLE IF NOT EXISTS paper_positions (
          id SERIAL PRIMARY KEY,
          symbol VARCHAR(30) UNIQUE NOT NULL,
          net_qty INTEGER NOT NULL DEFAULT 0,
          avg_price DOUBLE PRECISION NOT NULL DEFAULT 0,
          realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
          last_price DOUBLE PRECISION NULL,
          unrealized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
          updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """,
        # 5. paper_daily_pnl
        """
        CREATE TABLE IF NOT EXISTS paper_daily_pnl (
          id SERIAL PRIMARY KEY,
          symbol VARCHAR(30) NOT NULL,
          trading_date DATE NOT NULL,
          realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
          unrealized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
          mtm_price DOUBLE PRECISION NULL,
          created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
          UNIQUE(symbol, trading_date)
        );
        """,
        # 6. paper_accounts
        """
        CREATE TABLE IF NOT EXISTS paper_accounts (
          id SERIAL PRIMARY KEY,
          total_capital DOUBLE PRECISION NOT NULL DEFAULT 10000000.0,
          available_cash DOUBLE PRECISION NOT NULL DEFAULT 10000000.0,
          updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """,
        # 7. Initialize Balance if empty
        """
        INSERT INTO paper_accounts (id, total_capital, available_cash)
        SELECT 1, 10000000.0, 10000000.0
        WHERE NOT EXISTS (SELECT 1 FROM paper_accounts WHERE id = 1);
        """,
        # 8. Indexes
        "CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol_created ON paper_orders(symbol, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_paper_orders_status ON paper_orders(status);",
        "CREATE INDEX IF NOT EXISTS idx_paper_fills_symbol_ts ON paper_fills(symbol, timestamp DESC);"
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            conn.execute(text(cmd))
        conn.commit()
    print("✅ Paper trading tables initialized successfully.")

if __name__ == "__main__":
    init_paper_tables()
