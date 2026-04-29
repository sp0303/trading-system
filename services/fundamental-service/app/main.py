import logging
import nsepython
import json
import os
from fastapi import FastAPI, Query
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from typing import Optional
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Nifty Elite Fundamental Service")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "ok", "service": "fundamental-service"}

@app.get("/analysis")
def get_analysis(symbol: str = Query(...)):
    symbol = symbol.upper()
    try:
        with engine.connect() as conn:
            # 1. Fetch Fundamentals
            query = text("SELECT * FROM institutional_fundamentals WHERE symbol = :symbol")
            fund = conn.execute(query, {"symbol": symbol}).fetchone()
            
            # 2. Fetch Latest Price Context
            price_query = text("SELECT close FROM ohlcv_enriched WHERE symbol = :symbol ORDER BY timestamp DESC LIMIT 1")
            price_res = conn.execute(price_query, {"symbol": symbol}).fetchone()
            
            if not fund:
                return {"status": "error", "error": "No fundamental data for analysis"}

            fund_data = dict(fund._mapping)
            current_price = price_res[0] if price_res else 0
            
            pros = []
            cons = []

            # --- Logic Engine ---
            pe = fund_data.get('pe_ratio')
            pb = fund_data.get('pb_ratio')
            mcap = fund_data.get('market_cap')
            h52 = fund_data.get('high_52w')
            l52 = fund_data.get('low_52w')

            # Valuation
            if pe:
                if pe < 15: pros.append("Trading at a low P/E ratio compared to historical averages.")
                elif pe > 50: cons.append(f"High P/E ratio ({pe}) — stock may be overvalued.")

            if pb:
                if pb < 1.5: pros.append("Good valuation based on book value (Low P/B).")
                elif pb > 6: cons.append(f"Trading at {pb}x its book value (Premium valuation).")

            # Market Cap / Stability
            if mcap and mcap > 1000000000000: # 1 Lac Cr
                pros.append("Mega-cap stability — considered an institutional safe-haven.")
            
            # 52-Week Context
            if h52 and current_price:
                dist_from_high = ((h52 - current_price) / h52) * 100
                if dist_from_high < 5: cons.append("Stock is trading near its 52-week high.")
                elif dist_from_high > 40: pros.append("Significant correction from highs — potential value opportunity.")

            if l52 and current_price:
                dist_from_low = ((current_price - l52) / l52) * 100
                if dist_from_low < 10: pros.append("Trading near 52-week lows — possible bottoming out.")

            # Default if empty
            if not pros: pros.append("Maintain neutral institutional accumulation.")
            if not cons: cons.append("No major financial structural red-flags detected.")

            return {
                "status": "success",
                "symbol": symbol,
                "analysis": {
                    "pros": pros[:4], # Limit to 4
                    "cons": cons[:4]
                }
            }
    except Exception as e:
        logging.error(f"Analysis generation failed: {e}")
        return {"status": "error", "error": str(e)}

@app.get("/fundamentals")
def get_fundamentals(symbol: str = Query(...)):
    symbol = symbol.upper()
    
    # 🔹 1. TRY DATABASE FIRST (Institutional Source)
    try:
        with engine.connect() as conn:
            query = text("SELECT * FROM institutional_fundamentals WHERE symbol = :symbol")
            result = conn.execute(query, {"symbol": symbol}).fetchone()
            
            if result:
                data = dict(result._mapping)
                last_updated = data.pop('last_updated')
                
                # Check for staleness (24 hours)
                if last_updated and (datetime.now(last_updated.tzinfo) - last_updated) < timedelta(hours=24):
                    logging.info(f"Serving {symbol} from DB (Institutional Local).")
                    return {"status": "success", "data": data, "source": "database"}
                else:
                    logging.info(f"{symbol} in DB is stale. Refreshing from NSE.")
    except Exception as e:
        logging.error(f"Database lookup error: {e}")

    # 🔹 2. FETCH FROM NSE (Official Source)
    try:
        logging.info(f"Fetching institutional metrics from NSE for {symbol}...")
        raw_data = nsepython.nse_eq(symbol)
        
        if not raw_data or "info" not in raw_data:
             raise ValueError("Institutional data unavailable (NSE limit or invalid symbol)")

        info = raw_data.get("info", {})
        metadata = raw_data.get("metadata", {})
        price_info = raw_data.get("priceInfo", {})
        security_info = raw_data.get("securityInfo", {})
        
        # Calculate Professional Market Cap
        issued_size = security_info.get("issuedSize", 0)
        last_price = price_info.get("lastPrice", 0)
        market_cap = float(issued_size * last_price) if issued_size and last_price else None

        # Build consistent institutional data model
        data = {
            "symbol": symbol,
            "market_cap": market_cap,
            "pe_ratio": metadata.get("pdSymbolPe"),
            "pb_ratio": None, 
            "dividend_yield": None,
            "high_52w": price_info.get("weekHighLow", {}).get("max"),
            "low_52w": price_info.get("weekHighLow", {}).get("min"),
            "debt_to_equity": None,
            "return_on_equity": None,
            "sector": info.get("industry"),
            "long_summary": f"Official NSE listed entity: {info.get('companyName')}. Sector: {info.get('industry')}.",
        }

        # 🔹 PERSIST TO DATABASE
        try:
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
                logging.info(f"✅ Synced {symbol} fundamentals to Institutional DB.")
        except Exception as db_err:
            logging.error(f"Failed to persist metrics: {db_err}")

        return {"status": "success", "data": data, "source": "nse_live"}

    except Exception as e:
        logging.error(f"Institutional fetch failed: {e}")

    # 🔹 3. STALE FALLBACK
    try:
        with engine.connect() as conn:
            query = text("SELECT * FROM institutional_fundamentals WHERE symbol = :symbol")
            result = conn.execute(query, {"symbol": symbol}).fetchone()
            if result:
                data = dict(result._mapping)
                data.pop('last_updated', None)
                return {"status": "success", "data": data, "source": "stale_db"}
    except: pass

    return {"status": "error", "error": f"Metrics unavailable for {symbol}."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7008)
