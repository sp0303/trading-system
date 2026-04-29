"""
Institutional Signal Consumer.
Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

This service reacts to 'Golden Bars' (bars.1m) from Kafka,
fetches the enriched feature row from the DB, and sends to the
7-Strategy Engine & ML Models for signal generation.
"""
import asyncio
import os
import ujson as json
import logging
from aiokafka import AIOKafkaConsumer
import httpx
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Config
BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
IN_TOPIC = os.getenv("BARS_TOPIC", "bars.1m")
GROUP_ID = os.getenv("KAFKA_GROUP_CONSUMER", "nifty_elite_signal_consumer")
SIGNAL_SERVICE_URL = os.getenv("SIGNAL_SERVICE_URL", "http://localhost:7004")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading:trading@localhost:5433/trading_db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class SignalConsumer:
    def __init__(self):
        self.logger = logging.getLogger("SignalConsumer")
        self.client = httpx.AsyncClient(timeout=30)
        # DB engine to look up enriched features
        self.engine = create_engine(DATABASE_URL)

    def _get_enriched_features(self, symbol: str) -> dict:
        """
        Fetch the most recent enriched feature row for a symbol.
        This ensures the signal engine gets real technical indicators.
        """
        try:
            with self.engine.connect() as conn:
                row = conn.execute(text(
                    """
                    SELECT *
                    FROM ohlcv_enriched
                    WHERE symbol = :symbol
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """
                ), {"symbol": symbol}).fetchone()

                if row:
                    keys = row._mapping.keys()
                    features = dict(zip(keys, row))
                    # Convert timestamp to string for JSON serialization
                    if "timestamp" in features and features["timestamp"]:
                        features["timestamp"] = str(features["timestamp"])
                    return features
        except Exception as e:
            self.logger.error(f"Failed to fetch enriched features for {symbol}: {e}")
        return {}

    async def run(self):
        consumer = AIOKafkaConsumer(
            IN_TOPIC,
            bootstrap_servers=BROKER,
            enable_auto_commit=True,
            group_id=GROUP_ID,
            value_deserializer=lambda b: json.loads(b.decode())
        )

        await consumer.start()
        self.logger.info(f"✅ Signal Consumer started on topic '{IN_TOPIC}'")

        try:
            async for msg in consumer:
                bar = msg.value
                symbol = bar.get("symbol")
                if not symbol:
                    continue

                # Fetch enriched features from the DB
                features = self._get_enriched_features(symbol)

                if not features:
                    # Fall back to bare-bar features if DB has no data yet
                    self.logger.debug(f"No enriched features for {symbol}, using bar only")
                    features = {
                        "open": bar.get("o"),
                        "high": bar.get("h"),
                        "low": bar.get("l"),
                        "close": bar.get("c"),
                        "volume": bar.get("vol"),
                        "minutes_from_open": 0,
                    }

                timestamp = features.get("timestamp") or str(bar.get("ts"))

                payload = {
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "features": features,
                }

                try:
                    resp = await self.client.post(
                        f"{SIGNAL_SERVICE_URL}/process",
                        json=payload
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "signals_generated":
                            self.logger.info(
                                f"🚀 SIGNAL DETECTED for {symbol}: {data.get('alerts')}"
                            )
                    else:
                        self.logger.warning(
                            f"Signal service returned {resp.status_code} for {symbol}"
                        )
                except Exception as e:
                    self.logger.error(f"Error processing bar for {symbol}: {e}")

        finally:
            await consumer.stop()
            await self.client.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(SignalConsumer().run())
