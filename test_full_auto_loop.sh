#!/bin/bash
# Script to force-test the automatic order and exit loop

echo "🔍 Checking if services are running..."
ps aux | grep -v grep | grep "paper-trading-service/app/main" > /dev/null && echo "✅ Paper Trading Service is running" || echo "⚠️ Paper Trading Service NOT running"
ps aux | grep -v grep | grep "risk_manager" > /dev/null && echo "✅ Execution Service (Risk Manager) is running" || echo "⚠️ Execution Service NOT running"
ps aux | grep -v grep | grep "signal-service/app/main" > /dev/null && echo "✅ Signal Service is running" || echo "⚠️ Signal Service NOT running"

echo ""
echo "🚀 Injecting a TRIGGER BAR directly to Kafka (bars.1m)..."

# Use Python to publish directly to Kafka (no docker binary needed)
source trading-system/bin/activate
set -a; source .env; set +a

python3 - <<'PYEOF'
import asyncio
import ujson as json
import time
import os

async def inject():
    from aiokafka import AIOKafkaProducer
    broker = os.getenv("KAFKA_BROKER", "localhost:9092")
    producer = AIOKafkaProducer(bootstrap_servers=broker)
    await producer.start()
    bar = {
        "symbol": "SBIN",
        "o": 650, "h": 720, "l": 640, "c": 715,
        "vol": 900000,
        "ts": int(time.time())
    }
    await producer.send_and_wait("bars.1m", json.dumps(bar).encode())
    print(f"✅ Injected bar to bars.1m: {bar}")
    await producer.stop()

asyncio.run(inject())
PYEOF

echo ""
echo "📂 Tailing logs for 30 seconds - watch for TRADER ALERT..."
timeout 30s tail -f logs/signal.log logs/paper_api.log logs/risk_manager.log


