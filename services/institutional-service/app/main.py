import logging
import time
import os
from typing import Dict, Any, Optional

from fastapi import FastAPI, Query, HTTPException, Request
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from nsepython import nse_eq
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_fixed
from sqlalchemy import create_engine, text
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading:Trading%40123@localhost:5432/tradingsystem")
engine = create_engine(DATABASE_URL)

# ==============================
# 🔧 CONFIG
# ==============================
CACHE_TTL = 60  # seconds
CACHE_SIZE = 500

# Initialize cache
cache = TTLCache(maxsize=CACHE_SIZE, ttl=CACHE_TTL)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# FastAPI app
app = FastAPI(title="Nifty Elite Institutional flow V2")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ==============================
# 🔁 NSE FETCH (with retry)
# ==============================
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_nse_data(symbol: str) -> Dict[str, Any]:
    return nse_eq(symbol)

# ==============================
# 🧠 SIGNAL ENGINE
# ==============================
def compute_institutional_signal(delivery_pct, total_qty) -> Dict[str, Any]:
    score = 0
    reasoning = []

    if delivery_pct is not None:
        if delivery_pct > 60:
            score += 3
            reasoning.append("Very high delivery (strong accumulation)")
        elif delivery_pct > 45:
            score += 2
            reasoning.append("Above average delivery")
        elif delivery_pct > 35:
            score += 1
            reasoning.append("Moderate delivery")
        else:
            reasoning.append("Low delivery (speculative activity)")

    if total_qty is not None:
        if total_qty > 1_000_000:
            score += 2
            reasoning.append("High volume participation")
        elif total_qty > 300_000:
            score += 1
            reasoning.append("Moderate volume")

    if score >= 5:
        sentiment = "Strong Bullish"
    elif score >= 3:
        sentiment = "Bullish"
    elif score >= 1:
        sentiment = "Neutral"
    else:
        sentiment = "Bearish"

    return {
        "score": score,
        "sentiment": sentiment,
        "reasoning": reasoning
    }

# ==============================
# 📦 CORE SERVICE
# ==============================
@app.get("/institutional-flow")
def get_institutional_flow(symbol: str = Query(..., description="Stock symbol (e.g., RELIANCE)")):
    symbol = symbol.upper()

    # 🔹 1. Check cache first
    if symbol in cache:
        logging.info(f"[CACHE HIT] {symbol}")
        return {"status": "success", "data": cache[symbol], "source": "cache"}

    start_time = time.time()
    
    # 🔹 2. Try Live NSE Fetch
    try:
        eq_data = fetch_nse_data(symbol)
        delivery_info = eq_data.get("securityWiseDP", {})
        delivery_pct = delivery_info.get("deliveryToTradedQuantity")
        total_qty = delivery_info.get("quantityTraded")

        if delivery_pct is None or total_qty is None:
             raise Exception("NSE Delivery Data Incomplete (Off-Market or Rate-Limited)")

        signal = compute_institutional_signal(delivery_pct, total_qty)
        
        response_data = {
            "symbol": symbol,
            "delivery": {
                "percentage": delivery_pct,
                "quantity": int(total_qty * (delivery_pct/100)),
                "total_traded": total_qty
            },
            "signal": signal,
            "date": delivery_info.get("secWiseDPDate"),
            "latency_ms": round((time.time() - start_time) * 1000, 2)
        }

        # 🔹 PERSIST TO DATABASE (The "Source of Truth")
        try:
            with engine.connect() as conn:
                upsert_query = text("""
                    INSERT INTO institutional_flow (symbol, delivery_pct, total_qty, sentiment, score, reasoning, last_updated)
                    VALUES (:symbol, :delivery_pct, :total_qty, :sentiment, :score, :reasoning, CURRENT_TIMESTAMP)
                    ON CONFLICT (symbol) DO UPDATE SET
                        delivery_pct = EXCLUDED.delivery_pct,
                        total_qty = EXCLUDED.total_qty,
                        sentiment = EXCLUDED.sentiment,
                        score = EXCLUDED.score,
                        reasoning = EXCLUDED.reasoning,
                        last_updated = CURRENT_TIMESTAMP;
                """)
                conn.execute(upsert_query, {
                    "symbol": symbol,
                    "delivery_pct": delivery_pct,
                    "total_qty": total_qty,
                    "sentiment": signal["sentiment"],
                    "score": signal["score"],
                    "reasoning": signal["reasoning"]
                })
                conn.commit()
        except Exception as db_err:
            logging.error(f"Failed to persist institutional flow to DB: {db_err}")

        cache[symbol] = response_data
        return {"status": "success", "data": response_data, "source": "live"}

    except Exception as e:
        logging.warning(f"Live fetch failed for {symbol}: {e}. Attempting DB fallback.")

        # 🔹 3. Database Fallback (Institutional Source of Truth)
        try:
            with engine.connect() as conn:
                query = text("SELECT * FROM institutional_flow WHERE symbol = :symbol")
                result = conn.execute(query, {"symbol": symbol}).fetchone()
                if result:
                    row = dict(result._mapping)
                    response_data = {
                        "symbol": symbol,
                        "delivery": {
                            "percentage": row["delivery_pct"],
                            "quantity": int(row["total_qty"] * (row["delivery_pct"]/100)),
                            "total_traded": row["total_qty"]
                        },
                        "signal": {
                            "sentiment": row["sentiment"],
                            "score": row["score"],
                            "reasoning": row["reasoning"]
                        },
                        "date": row["last_updated"].strftime("%Y-%m-%d %H:%M"),
                        "latency_ms": 0.0
                    }
                    logging.info(f"Serving {symbol} from Institutional DB (Historical Fallback).")
                    return {"status": "success", "data": response_data, "source": "database"}
        except Exception as db_err:
            logging.error(f"DB fallback failed: {db_err}")

        # 🔹 4. Static Fallback (Hardcoded TOP STOCKS)
        TOP_STOCKS_FALLBACK = {
            "RELIANCE": {"delivery_pct": 58.2, "total_qty": 1200000},
            "TCS": {"delivery_pct": 62.1, "total_qty": 450000},
            "HDFCBANK": {"delivery_pct": 55.4, "total_qty": 2100000},
            "INFY": {"delivery_pct": 48.9, "total_qty": 900000},
            "ADANIENT": {"delivery_pct": 38.5, "total_qty": 1500000} # Added for user
        }

        if symbol in TOP_STOCKS_FALLBACK:
            fb = TOP_STOCKS_FALLBACK[symbol]
            signal = compute_institutional_signal(fb["delivery_pct"], fb["total_qty"])
            response_data = {
                "symbol": symbol,
                "delivery": {
                    "percentage": fb["delivery_pct"],
                    "quantity": int(fb["total_qty"] * (fb["delivery_pct"]/100)),
                    "total_traded": fb["total_qty"]
                },
                "signal": signal,
                "date": "OFFLINE_FALLBACK",
                "latency_ms": 0.0
            }
            return {"status": "success", "data": response_data, "source": "static_fallback"}

        raise HTTPException(status_code=503, detail="Institutional data unavailable (Off-Market)")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7009)