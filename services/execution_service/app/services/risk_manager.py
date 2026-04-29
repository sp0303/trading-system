"""
Institutional Risk Manager.
Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

Processes 'NEW' orders from Kafka, calculates position sizes based on 'conviction', 
and either APPROVES (sized) or REJECTS them before sending to the execution topic.
"""
import os
import asyncio
import time
import ujson as json
import yaml
import asyncpg
import logging
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from typing import Dict, Any, Tuple
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from urllib.parse import unquote
from dotenv import load_dotenv

load_dotenv()

# Metrics
APPROVED = Counter("risk_orders_approved_total", "Approved orders")
REJECTED = Counter("risk_orders_rejected_total", "Rejected orders")
FUNDS_TRADABLE = Gauge("risk_manager_tradable_equity_inr", "Tradable equity")

# Config from Env
BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
IN_TOPIC = os.getenv("IN_TOPIC", "orders")
OUT_TOPIC = os.getenv("OUT_TOPIC", "orders.sized")
GROUP_ID = os.getenv("KAFKA_GROUP", "nifty_elite_risk_manager")
DATABASE_URL = os.getenv("DATABASE_URL")
CONF_PATH = "config/risk_budget.yaml"

# Database Configuration (Structured fallback for Docker)
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "trading_db")
DB_USER = os.getenv("DB_USER", "trading")
DB_PASS = os.getenv("DB_PASS", "trading")

if DATABASE_URL and "://" in DATABASE_URL:
    try:
        clean_url = DATABASE_URL.split("://")[1]
        user_pass, host_port_db = clean_url.split("@")
        user, password = user_pass.split(":")
        user = unquote(user)
        password = unquote(password)
        host_port, db = host_port_db.split("/")
        host, port = host_port.split(":")
    except Exception:
        host, port, db, user, password = DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
else:
    host, port, db, user, password = DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS

class RiskManager:
    def __init__(self):
        self.conf = self._load_conf()
        self.logger = logging.getLogger("RiskManager")
        
    def _load_conf(self) -> Dict[str, Any]:
        with open(CONF_PATH, 'r') as f:
            return yaml.safe_load(f)

    def _pos_size(self, entry: float, stop: float, risk_rupees: float, tick: float) -> int:
        edge = max(abs(entry - stop), tick)
        return max(0, int(risk_rupees / edge))

    async def get_latest_price(self, pool, symbol: str) -> float:
        async with pool.acquire() as con:
            # Try to get from 1m bars first (Golden Bar)
            r = await con.fetchrow("SELECT c FROM bars_1m WHERE symbol=$1 ORDER BY ts DESC LIMIT 1", symbol)
            if r and r["c"]: return float(r["c"])
            
            # Fallback to enriched OHLCV
            r = await con.fetchrow("SELECT close FROM ohlcv_enriched WHERE symbol=$1 ORDER BY timestamp DESC LIMIT 1", symbol)
            return float(r["close"]) if r and r["close"] else 100.0

    async def run(self):
        try:
            start_http_server(int(os.getenv("METRICS_PORT", "8116")))
        except OSError:
            self.logger.warning("Metrics port already in use, skipping Prometheus server")
        pool = await asyncpg.create_pool(host=host, port=int(port), database=db, user=user, password=password)
        
        consumer = AIOKafkaConsumer(
            IN_TOPIC, bootstrap_servers=BROKER, enable_auto_commit=True,
            group_id=GROUP_ID, value_deserializer=lambda b: json.loads(b.decode()))
        
        producer = AIOKafkaProducer(bootstrap_servers=BROKER, acks="all", linger_ms=5)
        
        await consumer.start(); await producer.start()
        
        # Initialize metrics
        total_equity = float(self.conf.get("total_cash_inr", 1000000))
        holdback = float(self.conf.get("holdback_fraction", 0.1))
        FUNDS_TRADABLE.set(total_equity * (1.0 - holdback))
        
        self.logger.info("Risk Manager started ✅")

        try:
            async for msg in consumer:
                order = msg.value
                if order.get("status") != "NEW":
                    continue
                
                symbol = order["symbol"]
                conviction = order.get("risk_bucket", "LOW").upper()
                
                # Calculate funds
                total_equity = float(self.conf.get("total_cash_inr", 0))
                holdback = float(self.conf.get("holdback_fraction", 0.1))
                tradable = total_equity * (1.0 - holdback)
                FUNDS_TRADABLE.set(tradable)
                
                # Fetch reference price
                ref_px = await self.get_latest_price(pool, symbol)
                
                # Size based on conviction %
                bucket_conf = self.conf["buckets"].get(conviction, {"split": 0.1})
                bucket_budget = tradable * bucket_conf["split"]
                
                # Use stop loss if provided for precise sizing
                sig = (order.get("extra") or {}).get("signal") or {}
                entry = float(sig.get("entry_px") or ref_px)
                stop = sig.get("stop_px")
                
                if stop:
                    risk_pct = self.conf["risk_per_trade_pct"].get(conviction, 0.1)
                    risk_rupees = total_equity * (risk_pct / 100.0)
                    qty = self._pos_size(entry, float(stop), risk_rupees, self.conf.get("tick_size", 0.05))
                else:
                    # Fallback to monetary cap
                    strategy = order.get("strategy", "DEFAULT")
                    cap = self.conf["monetary_caps"].get(strategy, self.conf["monetary_caps"]["DEFAULT"])
                    qty = int(cap / max(ref_px, 0.01))
                
                # Apply hard caps
                max_qty = self.conf.get("per_symbol_max_qty", 1000)
                qty = min(qty, max_qty)
                
                if qty > 0:
                    order["qty"] = qty
                    order["status"] = "APPROVED"
                    order["extra"] = order.get("extra") or {}
                    order["extra"]["risk"] = {
                        "approved_qty": qty, 
                        "ref_price": ref_px,
                        "conviction": conviction
                    }
                    
                    async with pool.acquire() as con:
                        await con.execute(
                            "UPDATE orders SET qty=$2, status='APPROVED', extra=extra || $3::jsonb WHERE client_order_id=$1",
                            order["client_order_id"], qty, json.dumps({"risk": order["extra"]["risk"]})
                        )
                    
                    await producer.send(OUT_TOPIC, json.dumps(order).encode(), key=symbol.encode())
                    APPROVED.inc()
                    self.logger.info(f"Order {order['client_order_id']} APPROVED for {qty} shares")
                else:
                    async with pool.acquire() as con:
                        await con.execute(
                            "UPDATE orders SET status='REJECTED', extra=extra || $2::jsonb WHERE client_order_id=$1",
                            order["client_order_id"], json.dumps({"risk_reason": "insufficient_budget"})
                        )
                    REJECTED.inc()
                    self.logger.warning(f"Order {order['client_order_id']} REJECTED by Risk Manager")
                    
        finally:
            await consumer.stop(); await producer.stop(); await pool.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(RiskManager().run())
