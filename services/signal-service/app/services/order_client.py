"""
Kafka-based Order Client for Institutional Execution.
Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

This replaces the simple PaperTradingClient. Instead of direct DB writes, 
it pushes a 'NEW' order to Kafka for the Risk Manager to audit and size.
"""
import os
import ujson as json
import time
import logging
from aiokafka import AIOKafkaProducer
from dotenv import load_dotenv

load_dotenv()

class KafkaOrderClient:
    def __init__(self):
        self.broker = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.topic = os.getenv("ORDERS_TOPIC", "orders")
        self.producer = None
        self.logger = logging.getLogger("KafkaOrderClient")

    async def start(self):
        if not self.producer:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.broker,
                acks="all",
                linger_ms=5,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda v: v.encode('utf-8')
            )
            await self.producer.start()
            self.logger.info(f"Kafka Order Producer started on {self.broker} ✅")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            self.producer = None

    async def create_order(self, payload: dict):
        """
        Submits a NEW order to the Kafka pipeline.
        Payload should conform to the professional OMS schema.
        """
        if not self.producer:
            await self.start()
            
        symbol = payload["symbol"]
        
        # Structure the order for the Institutional OMS
        order = {
            "client_order_id": f"ELITE-{int(time.time()*1000)}",
            "ts": int(time.time()),
            "symbol": symbol,
            "side": payload["side"],
            "qty": payload.get("qty", 1), # Initial qty, Risk Manager will resize
            "order_type": "MKT",
            "strategy": payload.get("strategy_name", "UNKNOWN"),
            "risk_bucket": payload.get("conviction", "LOW"),
            "status": "NEW",
            "extra": {
                "source": "nifty_elite_signal_service",
                "regime": payload.get("regime"),
                "signal": payload.get("extra", {}), # Contains entry/stop
            }
        }
        
        try:
            await self.producer.send_and_wait(self.topic, order, key=symbol)
            self.logger.info(f"Order {order['client_order_id']} pushed to Kafka topic '{self.topic}'")
            return order
        except Exception as e:
            self.logger.error(f"Failed to push order to Kafka: {e}")
            return None
