"""
Kafka 'ticks' -> 'bars.1s' (Institutional Stream).
Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

This service consumes raw ticks, builds 1-second candles, and publishes them back to Kafka.
It also persists them to Postgres for historical depth.
"""
import asyncio
import os
import time
import ujson as json
import logging
from collections import defaultdict
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncpg
from prometheus_client import start_http_server, Counter, Histogram, Gauge
from dotenv import load_dotenv
from urllib.parse import unquote

load_dotenv()

# Kafka Config
BROKER    = os.getenv("KAFKA_BROKER", "localhost:9092")
IN_TOPIC  = os.getenv("IN_TOPIC", "ticks")
OUT_TOPIC = os.getenv("OUT_TOPIC", "bars.1s")
GROUP_ID  = os.getenv("KAFKA_GROUP", "nifty_elite_bars_1s")

# Database Config (Extracted from DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")
# Simple parser for postgresql://user:pass@host:port/db
try:
    # Remove protocol
    clean_url = DATABASE_URL.split("://")[1]
    # Split user:pass and host:port/db
    user_pass, host_port_db = clean_url.split("@")
    user, password = user_pass.split(":")
    
    # Decode URL-encoded characters (like %40 for @)
    user = unquote(user)
    password = unquote(password)
    
    # Split host:port and db
    host_port, db = host_port_db.split("/")
    host, port = host_port.split(":")
except Exception as e:
    logging.error(f"Failed to parse DATABASE_URL: {e}")
    # Fallbacks for safety
    host, port, db, user, password = "localhost", 5432, "tradingsystem", "trading", "Trading@123"

METRICS_PORT = int(os.getenv("METRICS_PORT", "8112"))
FLUSH_GRACE_SEC = 1 # More aggressive for institutional speed

DDL = """
CREATE TABLE IF NOT EXISTS bars_1s(
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
INSERT INTO bars_1s(symbol, ts, o, h, l, c, vol, n_trades)
VALUES($1, to_timestamp($2), $3, $4, $5, $6, $7, $8)
ON CONFLICT(symbol, ts) DO UPDATE
SET o=EXCLUDED.o, h=EXCLUDED.h, l=EXCLUDED.l, c=EXCLUDED.c,
    vol=bars_1s.vol + EXCLUDED.vol, n_trades=bars_1s.n_trades + EXCLUDED.n_trades;"""

# Metrics
BARS_WRITTEN   = Counter("bars_1s_written_total", "1s bars written to Postgres")
BARS_PUBLISHED = Counter("bars_1s_published_total", "1s bars published to Kafka")
TICKS_INGESTED = Counter("bars_1s_ticks_total", "Ticks consumed by builder")
TICK_LATENCY   = Histogram(
    "bars_1s_tick_latency_seconds",
    "Latency between tick event and builder processing",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)
OPEN_BARS      = Gauge("bars_1s_open_symbols", "Symbols with active 1s candles")

class Bar:
    __slots__ = ("o","h","l","c","vol","n_trades","sec")
    def __init__(self, px: float, sec: int, vol: int = 0):
        self.o=self.h=self.l=self.c=float(px)
        self.vol=int(vol); self.n_trades=1; self.sec=int(sec)
    def update(self, px: float, vol: int = 0):
        px=float(px); self.c=px; self.h=max(self.h,px); self.l=min(self.l,px)
        self.vol += int(vol); self.n_trades += 1

async def ensure_schema(pool):
    async with pool.acquire() as con:
        await con.execute(DDL)

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("BarBuilder1s")
    
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
        value_deserializer=lambda b: json.loads(b.decode()),
        key_deserializer=lambda b: b.decode() if b else None)
    
    producer = AIOKafkaProducer(bootstrap_servers=BROKER, acks="all", linger_ms=5)
    
    await consumer.start()
    await producer.start()
    logger.info("Kafka Consumer/Producer started ✅")

    bars = {} # symbol -> Bar
    
    async def flush_old_bars():
        while True:
            await asyncio.sleep(0.5)
            now_s = int(time.time())
            to_flush = []
            for sym, b in list(bars.items()):
                if b.sec <= (now_s - FLUSH_GRACE_SEC):
                    to_flush.append((sym, b))
            
            if to_flush:
                async with pool.acquire() as con:
                    async with con.transaction():
                        await con.executemany(UPSERT, [(s,br.sec,br.o,br.h,br.l,br.c,br.vol,br.n_trades) for s,br in to_flush])
                
                for s, br in to_flush:
                    payload = {"symbol": s, "tf": "1s", "ts": br.sec, "o": br.o, "h": br.h, "l": br.l, "c": br.c, "vol": br.vol}
                    await producer.send(OUT_TOPIC, json.dumps(payload).encode(), key=s.encode())
                    bars.pop(s, None)
                
                BARS_WRITTEN.inc(len(to_flush))
                BARS_PUBLISHED.inc(len(to_flush))
            
            OPEN_BARS.set(len(bars))

    asyncio.create_task(flush_old_bars())

    try:
        async for msg in consumer:
            r = msg.value
            sym = r["symbol"]
            px  = float(r["ltp"])
            vol = int(r.get("vol") or 0)
            event_ns = r.get("event_ts")
            sec = int(event_ns / 1_000_000_000) if event_ns else int(time.time())
            
            TICKS_INGESTED.inc()
            if event_ns:
                TICK_LATENCY.observe(max(0.0, (time.time_ns() - event_ns) / 1_000_000_000.0))
            
            if sym not in bars:
                bars[sym] = Bar(px, sec, vol)
            elif sec == bars[sym].sec:
                bars[sym].update(px, vol)
            else:
                # New second started, flush old one immediately
                old_bar = bars[sym]
                async with pool.acquire() as con:
                    await con.execute(UPSERT, sym, old_bar.sec, old_bar.o, old_bar.h, old_bar.l, old_bar.c, old_bar.vol, old_bar.n_trades)
                
                payload = {"symbol": sym, "tf": "1s", "ts": old_bar.sec, "o": old_bar.o, "h": old_bar.h, "l": old_bar.l, "c": old_bar.c, "vol": old_bar.vol}
                await producer.send(OUT_TOPIC, json.dumps(payload).encode(), key=sym.encode())
                
                bars[sym] = Bar(px, sec, vol)
                BARS_WRITTEN.inc(1)
                BARS_PUBLISHED.inc(1)

    finally:
        await consumer.stop()
        await producer.stop()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
