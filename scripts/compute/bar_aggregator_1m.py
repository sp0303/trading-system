"""
Kafka 'bars.1s' -> 'bars.1m' (The Golden Bar).
Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

This aggregator takes 1-second candles and produces standard 1-minute bars.
These are the primary bars used by the 7-Strategy Engine and ML Models.
"""
import asyncio
import os
import time
import ujson as json
import logging
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncpg
from prometheus_client import start_http_server, Counter, Histogram
from dotenv import load_dotenv
from urllib.parse import unquote

load_dotenv()

# Kafka Config
BROKER    = os.getenv("KAFKA_BROKER", "localhost:9092")
IN_TOPIC  = os.getenv("IN_TOPIC", "bars.1s")
OUT_TOPIC = os.getenv("OUT_TOPIC", "bars.1m")
GROUP_ID  = os.getenv("KAFKA_GROUP", "nifty_elite_bars_1m")

# Database Config (Extracted from DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")
try:
    clean_url = DATABASE_URL.split("://")[1]
    user_pass, host_port_db = clean_url.split("@")
    user, password = user_pass.split(":")
    
    # Decode URL-encoded characters (like %40 for @)
    user = unquote(user)
    password = unquote(password)
    
    host_port, db = host_port_db.split("/")
    host, port = host_port.split(":")
except Exception as e:
    logging.error(f"Failed to parse DATABASE_URL: {e}")
    host, port, db, user, password = "localhost", 5432, "tradingsystem", "trading", "Trading@123"

METRICS_PORT = int(os.getenv("METRICS_PORT", "8113"))
FLUSH_GRACE_SEC = 2 

DDL = """
CREATE TABLE IF NOT EXISTS bars_1m(
  symbol   text                     NOT NULL,
  ts       timestamptz              NOT NULL,
  o        double precision,
  h        double precision,
  l        double precision,
  c        double precision,
  vol      bigint,
  n_trades int,
  PRIMARY KEY(symbol, ts)
);"""

UPSERT = """
INSERT INTO bars_1m(symbol, ts, o, h, l, c, vol, n_trades)
VALUES($1, to_timestamp($2), $3, $4, $5, $6, $7, $8)
ON CONFLICT(symbol, ts) DO UPDATE SET
  o = EXCLUDED.o,
  h = GREATEST(bars_1m.h, EXCLUDED.h),
  l = LEAST(bars_1m.l, EXCLUDED.l),
  c = EXCLUDED.c,
  vol = bars_1m.vol + EXCLUDED.vol,
  n_trades = bars_1m.n_trades + EXCLUDED.n_trades;"""

# Metrics
BARS_WRITTEN    = Counter("bars_1m_written_total", "1m bars written to Postgres")
BARS_PUBLISHED  = Counter("bars_1m_published_total", "1m bars published to Kafka")
BATCH_FLUSH_SEC = Histogram("bars_1m_flush_seconds", "1m flush time", buckets=(0.01,0.05,0.1,0.5,1.0))

class MBar:
    __slots__=("start","o","h","l","c","vol","n")
    def __init__(self, start:int, o:float, h:float, l:float, c:float, vol:int, n:int):
        self.start=start; self.o=o; self.h=h; self.l=l; self.c=c; self.vol=vol; self.n=n
    def merge_1s(self, o,h,l,c,vol,n):
        if self.n==0: self.o=o
        self.c=c; self.h=max(self.h,h); self.l=min(self.l,l); self.vol+=vol; self.n+=n

def minute_start(sec:int)->int: return sec - (sec % 60)

async def ensure_schema(pool):
    async with pool.acquire() as con: await con.execute(DDL)

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("BarAggregator1m")
    
    start_http_server(METRICS_PORT)
    logger.info(f"Prometheus metrics at port {METRICS_PORT}")
    
    pool = await asyncpg.create_pool(
        host=host, port=int(port), database=db, user=user, password=password, 
        min_size=1, max_size=4
    )
    await ensure_schema(pool)
    logger.info("Database connection and schema verified.")

    consumer = AIOKafkaConsumer(
        IN_TOPIC, bootstrap_servers=BROKER, enable_auto_commit=True,
        auto_offset_reset="earliest", group_id=GROUP_ID,
        value_deserializer=lambda b: json.loads(b.decode()))
    
    producer = AIOKafkaProducer(bootstrap_servers=BROKER, acks="all", linger_ms=5)
    
    await consumer.start(); await producer.start()
    logger.info("Kafka Consumer/Producer started ✅")

    state = {} # (symbol, minute_start) -> MBar

    async def flush_old_minutes():
        while True:
            await asyncio.sleep(1.0)
            now_s = int(time.time())
            to_flush = []
            for k, mb in list(state.items()):
                sym, mstart = k
                if now_s >= mstart + 60 + FLUSH_GRACE_SEC:
                    to_flush.append((k, sym, mb))
            
            if to_flush:
                @BATCH_FLUSH_SEC.time()
                async def _do():
                    async with pool.acquire() as con:
                        async with con.transaction():
                            await con.executemany(UPSERT, [(sym, mb.start, mb.o, mb.h, mb.l, mb.c, mb.vol, mb.n) for k, sym, mb in to_flush])
                    
                    for k, sym, mb in to_flush:
                        payload = {"symbol": sym, "tf": "1m", "ts": mb.start, "o": mb.o, "h": mb.h, "l": mb.l, "c": mb.c, "vol": mb.vol, "n_trades": mb.n}
                        await producer.send(OUT_TOPIC, json.dumps(payload).encode(), key=sym.encode())
                        state.pop(k, None)
                    
                    BARS_WRITTEN.inc(len(to_flush))
                    BARS_PUBLISHED.inc(len(to_flush))
                await _do()

    asyncio.create_task(flush_old_minutes())

    async for msg in consumer:
        r = msg.value
        sym = r["symbol"]; sec = int(r["ts"]); ms = minute_start(sec)
        k = (sym, ms)
        
        if k not in state:
            state[k] = MBar(ms, float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), int(r["vol"]), int(r.get("n_trades", 1)))
        else:
            state[k].merge_1s(float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), int(r["vol"]), int(r.get("n_trades", 1)))

if __name__ == "__main__":
    asyncio.run(main())
