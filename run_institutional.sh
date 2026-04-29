#!/bin/bash
# Nifty Elite: Institutional Runner
# Motto: "Intelligence-Driven, Infrastructure-Hardened Execution."

echo "🛑 Stopping local services and Docker containers..."
pkill -f "app.main"
pkill -f "gateway/main.py"
pkill -f "scripts/ingestion"
pkill -f "scripts/compute"
pkill -f "bar_consumer"
pkill -f "intelligence-rust-service"
docker compose down > /dev/null 2>&1
sleep 2


mkdir -p logs

echo "⚛️ Building Frontend Dashboard..."
(cd frontend && npm install && npm run build)

echo "🏗️ Starting Infrastructure (Kafka, Redis, Postgres, Monitoring)..."

(cd infra && docker compose up -d)


# Wait for Kafka to be ready
echo "⏳ Waiting for Kafka & Database..."
sleep 5

echo "🚀 Activating Virtual Environment..."
source trading-system/bin/activate

# Load Environment Variables for local services
echo "🔐 Loading .env configuration..."
set -a; source .env; set +a

echo "🚀 Starting Nifty Elite Core Stack..."

export PYTHONPATH=$(pwd)


# 1. CORE INTELLIGENCE SERVICES
echo "   -> Model Ensemble & Signal Engine..."
(cd services/model-service && python3 -m app.main > ../../logs/model.log 2>&1 &)
(cd services/signal-service && python3 -m app.main > ../../logs/signal.log 2>&1 &)

echo "   -> Contextual Services (Intelligence [Rust], AI, Fundamental)..."
(cd services/intelligence-rust-service && ./target/debug/intelligence-rust-service > ../../logs/intelligence_rust.log 2>&1 &)
(cd services/fundamental-service && python3 -m app.main > ../../logs/fundamental.log 2>&1 &)
(cd services/institutional-service && python3 -m app.main > ../../logs/institutional.log 2>&1 &)
(cd services/ai-service && python3 -m app.main > ../../logs/ai.log 2>&1 &)


echo "   -> Institutional OMS & Risk Manager..."
(cd services/execution_service && python3 -m app.services.risk_manager > ../../logs/risk_manager.log 2>&1 &)

echo "   -> Dashboard Data Provider (Positions/Account)..."
(cd services/paper-trading-service && python3 -m app.main > ../../logs/paper_api.log 2>&1 &)

# 2. HIGH-PERFORMANCE DATA PIPELINE
echo "🌊 Starting High-Performance Data Pipeline..."
echo "   -> Angel One Ingestor..."
python3 scripts/ingestion/angel_one_ws.py > logs/ingestion.log 2>&1 &

echo "   -> 1s Bar Builder..."
python3 scripts/compute/bar_builder_1s.py > logs/compute_1s.log 2>&1 &

echo "   -> 1m Golden Bar Aggregator..."
python3 scripts/compute/bar_aggregator_1m.py > logs/compute_1m.log 2>&1 &

echo "   -> Live Enrichment Service (calculates technical indicators)..."
python3 scripts/compute/live_enrichment.py > logs/live_enrichment.log 2>&1 &

echo "   -> Signal Consumer (listens to bars.1m → triggers signal engine)..."
python3 -m services.signal-service.app.services.bar_consumer > logs/signal_consumer.log 2>&1 &

# 3. API GATEWAY
echo "🌐 Starting API Gateway..."
export GATEWAY_URL="http://localhost:8000"
python3 gateway/main.py > logs/gateway.log 2>&1 &


echo "===================================================="
echo "🎉 INFRASTRUCTURE & SERVICES ARE LIVE"
echo "===================================================="
echo "📍 API Gateway (Consolidated): http://localhost:8000"
echo "📍 Grafana (Observability):    http://localhost:3000"
echo "📍 Kafka-UI (Management):      http://localhost:8085"
echo "===================================================="
echo "Check logs/ directory for service-specific debugging."
