import os
import sys
import logging
import time
import yfinance as yf
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_active_symbols():
    with engine.connect() as conn:
        query = text("SELECT DISTINCT symbol FROM ohlcv_enriched")
        result = conn.execute(query)
        return [row[0] for row in result]

def fetch_and_save_fundamental(symbol):
    search_symbol = symbol if ".NS" in symbol else f"{symbol}.NS"
    try:
        ticker = yf.Ticker(search_symbol)
        info = ticker.info
        
        if not info or "symbol" not in str(info).lower():
            return False

        data = {
            "symbol": symbol,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("forwardPE") or info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
            "high_52w": info.get("fiftyTwoWeekHigh"),
            "low_52w": info.get("fiftyTwoWeekLow"),
            "debt_to_equity": info.get("debtToEquity"),
            "return_on_equity": info.get("returnOnEquity"),
            "sector": info.get("sector"),
            "long_summary": info.get("longBusinessSummary"),
        }

        with engine.connect() as conn:
            upsert_query = text("""
                INSERT INTO institutional_fundamentals (
                    symbol, market_cap, pe_ratio, pb_ratio, dividend_yield, 
                    high_52w, low_52w, debt_to_equity, return_on_equity, 
                    sector, long_summary, last_updated
                ) VALUES (
                    :symbol, :market_cap, :pe_ratio, :pb_ratio, :dividend_yield,
                    :high_52w, :low_52w, :debt_to_equity, :return_on_equity,
                    :sector, :long_summary, CURRENT_TIMESTAMP
                ) ON CONFLICT (symbol) DO UPDATE SET
                    market_cap = EXCLUDED.market_cap,
                    pe_ratio = EXCLUDED.pe_ratio,
                    pb_ratio = EXCLUDED.pb_ratio,
                    dividend_yield = EXCLUDED.dividend_yield,
                    high_52w = EXCLUDED.high_52w,
                    low_52w = EXCLUDED.low_52w,
                    debt_to_equity = EXCLUDED.debt_to_equity,
                    return_on_equity = EXCLUDED.return_on_equity,
                    sector = EXCLUDED.sector,
                    long_summary = EXCLUDED.long_summary,
                    last_updated = CURRENT_TIMESTAMP;
            """)
            conn.execute(upsert_query, data)
            conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error fetching {symbol}: {e}")
        return False

def sync_fundamentals():
    symbols = get_active_symbols()
    logging.info(f"🚀 Starting SLOW-DRIP fundamental sync for {len(symbols)} symbols...")
    
    success_count = 0
    for symbol in tqdm(symbols):
        if fetch_and_save_fundamental(symbol):
            success_count += 1
            # Slow-drip mode to stay under the radar
            logging.info(f"✅ Saved {symbol}. Waiting 30s...")
            time.sleep(30) 
        else:
            # If hit 429, wait much longer
            logging.warning(f"⚠️ Failed {symbol}. Cooling down for 120s...")
            time.sleep(120)
            
    logging.info(f"Sync complete. Updated {success_count} symbols.")

if __name__ == "__main__":
    sync_fundamentals()
