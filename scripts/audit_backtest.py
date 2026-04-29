import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def audit_latest_backtest():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 1. Get latest valid backtest_id (ignoring NULLs)
        result = conn.execute(text("SELECT backtest_id, COUNT(*) as trade_count FROM trade_signals WHERE backtest_id IS NOT NULL GROUP BY backtest_id ORDER BY MAX(created_at) DESC LIMIT 1"))
        row = result.fetchone()
        
        if not row:
            print("❌ No valid backtest signals found in trade_signals table (all IDs are NULL or table is empty).")
            return

        backtest_id = row[0]
        trade_count = row[1]
        
        print(f"==========================================")
        print(f"📊 BACKTEST AUDIT: {backtest_id}")
        print(f"==========================================")
        print(f"Total Trades: {trade_count}")
        
        # 2. Get strategy breakdown
        query = text(f"SELECT strategy_name, direction, COUNT(*) as signal_count FROM trade_signals WHERE backtest_id = :bt_id GROUP BY strategy_name, direction")
        df = pd.read_sql(query, conn, params={"bt_id": backtest_id})
        print("\n📈 Strategy Breakdown:")
        if not df.empty:
            print(df.to_string(index=False))
        else:
            print("No trades recorded for this backtest ID.")
        
        # 3. Get probability and target statistics
        query = text(f"SELECT AVG(probability) as avg_prob, AVG(ABS(entry - target_l1)/entry*100) as avg_l1_pct FROM trade_signals WHERE backtest_id = :bt_id")
        df_stats = pd.read_sql(query, conn, params={"bt_id": backtest_id})
        
        avg_prob = df_stats['avg_prob'].iloc[0]
        avg_l1 = df_stats['avg_l1_pct'].iloc[0]
        
        print("\n💎 Signal Quality:")
        if avg_prob is not None:
            print(f"Average Win Probability: {avg_prob:.2%}")
            print(f"Average L1 Target Dist: {avg_l1:.2f}%")
        else:
            print("No probability statistics available.")
        
        # 4. Sample trades
        query = text(f"SELECT symbol, timestamp, strategy_name, direction, entry, target_l1 FROM trade_signals WHERE backtest_id = :bt_id LIMIT 5")
        df_sample = pd.read_sql(query, conn, params={"bt_id": backtest_id})
        print("\n🔍 Sample Trades:")
        if not df_sample.empty:
            print(df_sample.to_string(index=False))
        else:
            print("No samples available.")

if __name__ == "__main__":
    audit_latest_backtest()
