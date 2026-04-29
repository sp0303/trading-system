"""
Institutional Order Management System (OMS).
Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

Handles idempotent order upserts and state transitions with a full audit trail.
"""
import hashlib
import json
import asyncpg
import time
import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL")
try:
    clean_url = DATABASE_URL.split("://")[1]
    user_pass, host_port_db = clean_url.split("@")
    user, password = user_pass.split(":")
    host_port, db = host_port_db.split("/")
    host, port = host_port.split(":")
except Exception:
    host, port, db, user, password = "localhost", 5432, "tradingsystem", "trading", "Trading@123"

VALID_TRANSITIONS = {
  "NEW": {"ACK", "REJECTED", "APPROVED"},
  "APPROVED": {"ACK", "REJECTED", "FILLED", "CANCELED"},
  "ACK": {"PARTIAL", "FILLED", "CANCELED", "REJECTED"},
  "PARTIAL": {"PARTIAL", "FILLED", "CANCELED", "REJECTED"}
}

def _audit_hash(o: Dict[str, Any]) -> str:
    core = {
        "client_order_id": o["client_order_id"],
        "ts": int(o["ts"]),
        "symbol": o["symbol"],
        "side": o["side"],
        "qty": int(o["qty"]),
        "order_type": o["order_type"],
        "strategy": o["strategy"],
        "risk_bucket": o["risk_bucket"]
    }
    s = json.dumps(core, sort_keys=True, separators=(",",":"))
    return hashlib.sha256(s.encode()).hexdigest()

class OMS:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.logger = logging.getLogger("OMS")

    async def upsert_new(self, order: Dict[str, Any]) -> None:
        """Insert NEW order if absent; idempotent."""
        order = dict(order)
        if "ts" not in order or order["ts"] is None:
            order["ts"] = time.time()
        
        order["client_order_id"] = str(order.get("client_order_id") or "").strip()
        if not order["client_order_id"]:
            raise ValueError("order missing client_order_id")
            
        order["symbol"] = str(order.get("symbol") or "").strip()
        order["side"] = str(order.get("side") or "").upper()
        order["order_type"] = str(order.get("order_type") or "MKT").upper()
        order["strategy"] = str(order.get("strategy") or "UNKNOWN")
        order["risk_bucket"] = str(order.get("risk_bucket") or "MED").upper()
        order["qty"] = int(order.get("qty") or 0)
        order["status"] = order.get("status", "NEW")
        order["audit_hash"] = _audit_hash(order)
        
        sql = """
        INSERT INTO orders(client_order_id, ts, symbol, side, qty, order_type, strategy, risk_bucket, status, extra, audit_hash)
        VALUES($1, to_timestamp($2), $3, $4, $5, $6, $7, $8, 'NEW', $9, $10)
        ON CONFLICT (client_order_id) DO NOTHING;
        """
        
        async with self.pool.acquire() as con:
            async with con.transaction():
                result = await con.execute(sql, order["client_order_id"], int(order["ts"]),
                                  order["symbol"], order["side"], int(order["qty"]),
                                  order["order_type"], order["strategy"], order["risk_bucket"],
                                  json.dumps(order.get("extra") or {}), order["audit_hash"])
                
                # Only insert audit row if a new order was actually created
                if "INSERT 0 1" in result:
                    await con.execute(
                        "INSERT INTO order_audit(client_order_id, from_st, to_st, note, meta) VALUES($1,$2,$3,$4,$5)",
                        order["client_order_id"], None, "NEW", "System creation", json.dumps({})
                    )
                    self.logger.info(f"Order {order['client_order_id']} created in OMS")

    async def transition(self, coid: str, to_state: str, note: str = "", meta: Optional[Dict[str, Any]] = None) -> None:
        """Apply a valid state transition with audit trail."""
        meta = meta or {}
        async with self.pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow("SELECT status FROM orders WHERE client_order_id=$1 FOR UPDATE", coid)
                if not row:
                    raise ValueError(f"Unknown order {coid}")
                
                cur = row["status"]
                if cur == to_state:
                    return
                
                if cur not in VALID_TRANSITIONS or to_state not in VALID_TRANSITIONS[cur]:
                    if cur in ("FILLED", "CANCELED", "REJECTED"):
                        return
                    raise ValueError(f"Invalid transition {cur} -> {to_state} for {coid}")
                
                await con.execute("UPDATE orders SET status=$1, last_update=now() WHERE client_order_id=$2",
                                  to_state, coid)
                await con.execute(
                    "INSERT INTO order_audit(client_order_id, from_st, to_st, note, meta) VALUES($1,$2,$3,$4,$5)",
                    coid, cur, to_state, note, json.dumps(meta)
                )
                self.logger.info(f"Order {coid} transitioned: {cur} -> {to_state}")
