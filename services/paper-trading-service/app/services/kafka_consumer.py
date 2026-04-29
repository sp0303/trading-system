import os
import asyncio
import ujson as json
import logging
from aiokafka import AIOKafkaConsumer
from .oms import OMS
from ..models.database import SessionLocal

class InstitutionalOrderConsumer:
    def __init__(self):
        self.broker = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.topic = os.getenv("OUT_TOPIC", "orders.sized")
        self.group_id = os.getenv("KAFKA_GROUP_PAPER", "paper_trading_executor")
        self.logger = logging.getLogger("InstitutionalOrderConsumer")
        self.running = False

    async def start(self):
        self.logger.info(f"Starting Institutional Order Consumer on topic: {self.topic}")
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.broker,
            group_id=self.group_id,
            enable_auto_commit=True,
            value_deserializer=lambda b: json.loads(b.decode())
        )
        await self.consumer.start()
        self.running = True
        asyncio.create_task(self.run())

    async def stop(self):
        self.running = False
        if self.consumer:
            await self.consumer.stop()

    async def run(self):
        self.logger.info("Institutional Order Consumer loop started ✅")
        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                
                order_data = msg.value
                self.logger.info(f"Received approved order: {order_data.get('client_order_id')}")
                
                # Execute in a new DB session
                db = SessionLocal()
                try:
                    oms = OMS(db)
                    oms.execute_institutional_order(order_data)
                    self.logger.info(f"Successfully executed institutional order: {order_data.get('client_order_id')}")
                except Exception as e:
                    self.logger.error(f"Failed to execute institutional order: {e}")
                finally:
                    db.close()
        except Exception as e:
            self.logger.error(f"Consumer loop error: {e}")
        finally:
            self.logger.info("Institutional Order Consumer loop stopped.")
