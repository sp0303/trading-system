"""
Angel One SmartWebSocketV2 -> Kafka 'ticks' topic.
Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

This script handles the high-performance streaming backbone for the Nifty Elite stack.
It maps NSE/NFO symbols to tokens and pushes minimal tick data to Kafka.

Usage:
  KAFKA_BROKER=localhost:9092 python scripts/ingestion/angel_one_ws.py
"""
import os
import json
import time
import queue
import threading
import asyncio
import logging
import ujson
from datetime import datetime, timezone
from typing import List, Dict, Set

from prometheus_client import Counter, Gauge, Histogram, start_http_server
from aiokafka import AIOKafkaProducer
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from dotenv import load_dotenv

# Force WebSocket V2 to use secure WSS protocol
SmartWebSocketV2.ROOT_URI = "wss://smartapisocket.angelone.in/smart-stream"

# Add project root to path for shared imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from services.data_service.app.services.angel_one_client import AngelOneClient

load_dotenv()

# Configuration
BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC = os.getenv("TICKS_TOPIC", "ticks")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8111"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Logging Setup
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AngelOneWS")

# Prometheus Metrics
QUEUE_DEPTH = Gauge("angel_queue_depth", "Number of ticks buffered for Kafka dispatch")
TICKS_RECEIVED = Counter("angel_ticks_received_total", "Ticks received from exchange", ["symbol"])
TICKS_PROCESSED = Counter("angel_ticks_processed_total", "Ticks forwarded to Kafka", ["symbol"])
TICKS_DROPPED = Counter("angel_ticks_dropped_total", "Ticks dropped due to full queue")
TICK_LATENCY = Histogram(
    "angel_tick_latency_seconds",
    "Latency between exchange timestamp and Kafka publish",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 5),
)

class AngelOneKafkaProducer:
    def __init__(self):
        self.client = AngelOneClient()
        self.queue = queue.Queue(maxsize=10000)
        self.symmap = {} # token -> symbol
        self.tokens_to_subscribe = []
        self.sws = None
        self.last_pong_at = time.time()
        
    async def drain_to_kafka(self):
        """Async worker to take ticks from queue and push to Kafka."""
        logger.info(f"Connecting to Kafka at {BROKER}...")
        producer = AIOKafkaProducer(
            bootstrap_servers=BROKER, 
            acks="all", 
            linger_ms=5,
            value_serializer=lambda v: ujson.dumps(v).encode('utf-8'),
            key_serializer=lambda v: v.encode('utf-8')
        )
        await producer.start()
        logger.info("Kafka Producer started ✅")
        
        try:
            while True:
                try:
                    # Non-blocking get with timeout
                    batch = []
                    while not self.queue.empty() and len(batch) < 500:
                        batch.append(self.queue.get_nowait())
                    
                    if not batch:
                        await asyncio.sleep(0.01)
                        continue
                        
                    for tick in batch:
                        token = tick.get('token')
                        symbol = self.symmap.get(token, str(token))
                        
                        # Angel One Mode 3 (QUOTE) Tick Format
                        ltp = float(tick.get('last_traded_price', 0) / 100.0)
                        vol = int(tick.get('vng_volume', 0))
                        
                        ts_ms = tick.get('exchange_timestamp', int(time.time() * 1000))
                        ns = ts_ms * 1_000_000
                        
                        latency = (time.time() - (ts_ms / 1000.0))
                        TICK_LATENCY.observe(max(0, latency))
                        
                        msg = {
                            "symbol": symbol,
                            "event_ts": ns,
                            "ltp": ltp,
                            "vol": vol,
                            "source": "angel"
                        }
                        
                        await producer.send(TOPIC, value=msg, key=symbol)
                        TICKS_PROCESSED.labels(symbol).inc()
                    
                    QUEUE_DEPTH.set(self.queue.qsize())
                        
                except Exception as e:
                    logger.error(f"Error in Kafka drain: {e}")
                    await asyncio.sleep(1)
        finally:
            await producer.stop()

    def on_message(self, ws, message):
        """Standard callback for SmartWebSocketV2."""
        if not message or not isinstance(message, dict):
            return
            
        token = message.get('token')
        symbol = self.symmap.get(token, "UNKNOWN")
        TICKS_RECEIVED.labels(symbol).inc()
        
        try:
            self.queue.put_nowait(message)
            QUEUE_DEPTH.set(self.queue.qsize())
        except queue.Full:
            TICKS_DROPPED.inc()

    def on_data(self, ws, data):
        """Binary data callback."""
        if data and isinstance(data, dict):
            self.on_message(ws, data)

    def on_open(self, ws):
        logger.info(f"WebSocket Connection Opened ✅ (Total Tokens: {len(self.tokens_to_subscribe)})")
        try:
            # Batching to avoid "Text message too large" error (limit is 65535 bytes)
            # 500 tokens per batch is a safe limit for Angel One SmartStream
            chunk_size = 20
            tokens = list(self.tokens_to_subscribe) # Use a copy to prevent mutation issues
            
            for i in range(0, len(tokens), chunk_size):
                chunk = tokens[i:i + chunk_size]
                subscription_list = [{"exchangeType": 1, "tokens": chunk}]
                
                logger.info(f"Subscribing to batch {i//chunk_size + 1} ({len(chunk)} tokens)...")
                if self.sws:
                    self.sws.subscribe(correlation_id=f"nifty_elite_{i}", mode=3, token_list=subscription_list)
                else:
                    ws.subscribe(correlation_id=f"nifty_elite_{i}", mode=3, token_list=subscription_list)
                
                # Small sleep to avoid flooding the socket/server immediately on open
                time.sleep(0.1)
                
            logger.info(f"Successfully sent subscription requests for all {len(tokens)} tokens.")
        except Exception as e:
            logger.error(f"Failed to subscribe in on_open: {e}")

    def on_error(self, ws, error):
        logger.error(f"WebSocket Error: {error}")

    def on_close(self, ws, *args):
        logger.info(f"WebSocket Closed: {args}")

    def run(self):
        """Main entry point."""
        start_http_server(METRICS_PORT)
        logger.info(f"Prometheus metrics at port {METRICS_PORT}")

        if not self.client.login():
            logger.error("Failed to login to Angel One. Exiting.")
            return
        
        if not self.client.load_token_master():
            logger.error("Failed to load Scrip Master. Exiting.")
            return

        data_dir = "/home/sumanth/Desktop/trading-system/data/enriched_data_v2_nifty50"
        if os.path.exists(data_dir):
            symbols = [f.replace("_enriched.parquet", "").replace(".parquet", "") 
                       for f in os.listdir(data_dir) if f.endswith('.parquet')]
            logger.info(f"Dynamic Universe: Identified {len(symbols)} symbols from data directory.")
        else:
            symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT"]
            logger.warning(f"Data directory {data_dir} not found. Using fallback list.")

        for sym in symbols:
            info = self.client.get_token_info(sym)
            if info:
                token = info['token']
                self.symmap[token] = sym
                self.tokens_to_subscribe.append(token)
                logger.info(f"Prepared ticker for {sym} ({token})")

        auth_token = self.client.smart_api.access_token
        feed_token = self.client.smart_api.feed_token
        
        if not feed_token:
            logger.info("Feed token missing, fetching explicitly...")
            feed_token = self.client.smart_api.getfeedToken()
            self.client.smart_api.feed_token = feed_token

        self.sws = SmartWebSocketV2(auth_token, self.client.api_key, self.client.client_id, feed_token)
        
        # Monkey-patch _on_close to handle variable arguments and avoid NoneType race conditions
        def patched_on_close(instance, *args, **kwargs):
            try:
                if instance is not None:
                    return instance.on_close(*args, **kwargs)
            except Exception as e:
                logger.debug(f"Ignored error in patched_on_close: {e}")
        
        import types
        self.sws._on_close = types.MethodType(patched_on_close, self.sws)
        
        # Watchdog logic
        def patched_on_pong(ws, data):
            self.last_pong_at = time.time()

        self.sws.on_pong = patched_on_pong
        self.sws.on_open = self.on_open
        self.sws.on_message = self.on_message
        self.sws.on_error = self.on_error
        self.sws.on_close = self.on_close
        self.sws.on_data = self.on_data

        def run_ws():
            while True:
                try:
                    logger.info(f"Connecting to WebSocket at {self.sws.ROOT_URI}...")
                    self.last_pong_at = time.time()
                    self.sws.connect()
                except Exception as e:
                    logger.error(f"WebSocket execution error: {e}")
                
                logger.warning("WebSocket disconnected. Reconnecting in 5 seconds...")
                time.sleep(5)

        def watchdog():
            while True:
                time.sleep(30)
                if time.time() - self.last_pong_at > 60:
                    logger.warning("WebSocket Watchdog: No pong received for 60s. Forcing close...")
                    try:
                        if self.sws and self.sws.wsapp:
                            self.sws.wsapp.close()
                    except Exception as e:
                        logger.error(f"Watchdog failed to close connection: {e}")

        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()

        watch_thread = threading.Thread(target=watchdog, daemon=True)
        watch_thread.start()

        asyncio.run(self.drain_to_kafka())

if __name__ == "__main__":
    producer = AngelOneKafkaProducer()
    producer.run()
