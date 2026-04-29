#!/bin/bash

echo "🛑 Stopping all existing trading-system microservices..."
pkill -f "app/main.py"
pkill -f "app.main"
pkill -f "gateway/main.py"
pkill -f "intelligence-rust-service"
sleep 2

echo "✅ All services stopped."

echo "🏗️  Building Frontend..."
(cd frontend && npm run build > ../logs/frontend_build.log 2>&1)
echo "✅ Frontend built."

echo "🚀 Starting Backend Microservices..."

export PYTHONPATH=$(pwd)

# Activate Virtual Environment
source trading-system/bin/activate

# Core Services
(cd services/model-service && python3 -m app.main > ../../logs/model.log 2>&1 &)
(cd services/signal-service && python3 -m app.main > ../../logs/signal.log 2>&1 &)

# Intelligence Services
(cd services/intelligence-rust-service && ./target/debug/intelligence-rust-service > ../../logs/intelligence_rust.log 2>&1 &)
(cd services/fundamental-service && python3 -m app.main > ../../logs/fundamental.log 2>&1 &)
(cd services/institutional-service && python3 -m app.main > ../../logs/institutional.log 2>&1 &)
(cd services/ai-service && python3 -m app.main > ../../logs/ai.log 2>&1 &)
(cd services/paper-trading-service && python3 -m app.main > ../../logs/paper.log 2>&1 &)

echo "⏳ Waiting for services to initialize..."
sleep 3

echo "🌐 Starting API Gateway..."
python3 gateway/main.py > logs/gateway.log 2>&1 &

echo "====================================="
echo "🎉 All services are now running!"
echo "📍 Local Access (Consolidated): http://127.0.0.1:8000"
echo "🛠️  Dev Access (HMR): http://localhost:5173 (Run 'npm run dev' separately)"
echo "🚀 Cloudflare Tunnel: Run 'cloudflared tunnel run trading-tunnel'"
echo "====================================="
