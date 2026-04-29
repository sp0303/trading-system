import asyncio
import os
import ujson as json
import logging
import pandas as pd
import numpy as np
from aiokafka import AIOKafkaConsumer
import asyncpg
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from urllib.parse import unquote
import sys

# Add project root to path for shared imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.feature_engineer import FeatureEngineer

load_dotenv()

# Kafka Config
BROKER    = os.getenv("KAFKA_BROKER", "localhost:9092")
IN_TOPIC  = "bars.1m"
GROUP_ID  = "live_enrichment_service"

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL")
try:
    clean_url = DATABASE_URL.split("://")[1]
    user_pass, host_port_db = clean_url.split("@")
    user, password = user_pass.split(":")
    user = unquote(user)
    password = unquote(password)
    host_port, db = host_port_db.split("/")
    host, port = host_port.split(":")
except Exception as e:
    logging.error(f"Failed to parse DATABASE_URL: {e}")
    host, port, db, user, password = "localhost", 5432, "tradingsystem", "trading", "Trading@123"

# Enrichment Window (rows needed for indicators like RSI-14, MACD, etc.)
WINDOW_SIZE = 200 

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LiveEnrichment")

class LiveEnrichmentService:
    def __init__(self):
        self.engine = FeatureEngineer()
        self.pool = None
        self.history_cache = {} # symbol -> DataFrame
        self.db_columns = []

    async def start(self):
        self.pool = await asyncpg.create_pool(
            host=host, port=int(port), database=db, user=user, password=password,
            min_size=1, max_size=10
        )
        logger.info("Connected to Postgres ✅")
        
        self.db_columns = await self._get_db_columns()
        logger.info(f"Verified {len(self.db_columns)} database columns.")

        consumer = AIOKafkaConsumer(
            IN_TOPIC, bootstrap_servers=BROKER,
            group_id=GROUP_ID,
            auto_offset_reset="latest",
            value_deserializer=lambda b: json.loads(b.decode())
        )
        await consumer.start()
        logger.info(f"Subscribed to {IN_TOPIC} ✅")

        try:
            async for msg in consumer:
                bar = msg.value
                await self.process_bar(bar)
        finally:
            await consumer.stop()
            await self.pool.close()

    async def get_history(self, symbol):
        """Fetch last N bars from DB to initialize enrichment cache."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT timestamp, open, high, low, close, volume 
                FROM ohlcv_enriched 
                WHERE symbol = $1 
                ORDER BY timestamp DESC 
                LIMIT $2
                """,
                symbol, WINDOW_SIZE
            )
            if not rows:
                return pd.DataFrame()
            
            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = df.sort_values('timestamp')
            return df

    async def _get_db_columns(self):
        """Fetch valid column names from the database schema."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'ohlcv_enriched'"
            )
            return [r['column_name'] for r in rows]

    async def process_bar(self, bar):
        symbol = bar['symbol']
        ts = datetime.fromtimestamp(bar['ts'], tz=timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)
        
        # 1. Ensure we have history
        if symbol not in self.history_cache:
            logger.info(f"Initializing cache for {symbol}")
            self.history_cache[symbol] = await self.get_history(symbol)

        # 2. Append new bar
        new_row = pd.DataFrame([{
            'timestamp': ts,
            'open': float(bar['o']),
            'high': float(bar['h']),
            'low': float(bar['l']),
            'close': float(bar['c']),
            'volume': float(bar['vol'])
        }])
        
        hist = self.history_cache[symbol]
        
        # Check if this timestamp already exists (prevent duplicates in cache)
        if not hist.empty and hist['timestamp'].iloc[-1] >= ts:
            return

        updated_hist = pd.concat([hist, new_row]).tail(WINDOW_SIZE)
        self.history_cache[symbol] = updated_hist

        # 3. Enrich
        try:
            # We need at least some data to calculate indicators
            if len(updated_hist) < 20:
                return

            enriched_df = self.engine.enrich_data(updated_hist, symbol)
            last_row = enriched_df.iloc[-1]
            
            # 4. Upsert to Postgres
            await self.upsert_enriched(last_row)
            logger.debug(f"Enriched and stored {symbol} at {ts}")
        except Exception as e:
            logger.error(f"Enrichment failed for {symbol}: {e}")

    async def upsert_enriched(self, row):
        # Prepare columns and values
        # We exclude 'id' as it's auto-increment
        # Filter data to only include columns that exist in the DB
        data = {k: v for k, v in row.to_dict().items() if k in self.db_columns and k != 'id'}
        
        cols = list(data.keys())
        vals = [data[c] for c in cols]
        
        # Convert types for Postgres (asyncpg is strict)
        processed_vals = []
        for v in vals:
            if isinstance(v, (np.int64, np.int32)):
                processed_vals.append(int(v))
            elif isinstance(v, (np.float64, np.float32)):
                if np.isnan(v) or np.isinf(v):
                    processed_vals.append(None)
                else:
                    processed_vals.append(float(v))
            elif isinstance(v, (datetime, pd.Timestamp)):
                processed_vals.append(v)
            elif hasattr(v, 'date') and callable(getattr(v, 'date', None)):
                # Handle cases where it might be a date-like object but not exactly datetime
                processed_vals.append(str(v))
            elif isinstance(v, (pd.Series, np.ndarray)):
                # If a series/array leaked in, take the last value or first
                processed_vals.append(None)
            elif hasattr(v, 'isoformat'): # Catch any other date/time objects
                processed_vals.append(str(v))
            else:
                processed_vals.append(v)

        col_str = ", ".join(cols)
        placeholder_str = ", ".join([f"${i+1}" for i in range(len(cols))])
        update_str = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c not in ['symbol', 'timestamp']])

        query = f"""
        INSERT INTO ohlcv_enriched ({col_str})
        VALUES ({placeholder_str})
        ON CONFLICT (symbol, timestamp) 
        DO UPDATE SET {update_str};
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, *processed_vals)

if __name__ == "__main__":
    service = LiveEnrichmentService()
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
