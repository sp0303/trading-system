# Nifty Elite: Institutional Trading Ecosystem (v2)
**Motto**: *"Intelligence-Driven, Infrastructure-Hardened Execution."*

Nifty Elite is a professional-grade, event-driven algorithmic trading platform designed for high-frequency data ingestion, multi-model AI reasoning, and institutional order management. It combines a high-performance Kafka backbone with Gemma-powered AI validation to ensure every trade is backed by both technical precision and contextual intelligence.

---

## 🏛️ System Architecture

The platform is built on a "Intelligence-Driven Mesh" architecture, moving away from traditional polling to a reactive, event-driven flow.

### 1. The Senses (Ingestion Layer)
- **Angel One WS**: High-performance WebSocket producer (`angel_one_ws.py`) streaming real-time exchange ticks into Kafka.
- **Kafka Backbone**: Serves as the central nervous system, distributing raw `ticks` to compute workers.

### 2. The Pulse (Compute & Aggregation)
- **1s Builder**: Aggregates raw ticks into 1-second snapshots.
- **Golden Bar Aggregator**: Compiles 1s bars into "Golden 1m Bars" (`bars.1m`), which are the primary input for strategies.
- **Persistence**: High-throughput storage in Postgres via `asyncpg`.

### 3. The Brain (Intelligence Layer)
- **7-Strategy Engine**: Runs 6 core strategies (ORB, Momentum, Reversion, etc.) plus a Meta-Regime Classifier.
- **10-Model Ensemble**: An ML layer providing probability and conviction scores for every signal.
- **AI Thesis Validation**: Every signal is audited by a **Gemma:2b** LLM that analyzes News, Sentiment, and Institutional Flow before allowing an order.

### 4. The Guardrails (Risk & Execution)
- **Risk Manager**: Budget-aware position sizing based on AI conviction levels and strategy-specific caps.
- **Institutional OMS**: An Idempotent Order Management System with a strict state-transition engine (NEW -> APPROVED -> FILLED) and immutable audit trails.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Infrastucture** | Kafka, Zookeeper, Redis, Docker Compose |
| **Backend Logic** | Python 3.12+, FastAPI, AIOKafka, Asyncpg |
| **Intelligence** | Ollama (Gemma:2b), Scikit-Learn Ensemble |
| **Observability** | Prometheus, Grafana |
| **Database** | PostgreSQL (Institutional Schema) |

---

## 🚀 Getting Started

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Ollama (running locally with `gemma:2b`)

### 2. Infrastructure Launch
Initialize the core backbone:
```bash
cd infra
docker compose up -d
```
*Access Kafka-UI at [http://localhost:8085](http://localhost:8085)*

### 3. Service Execution
Follow the institutional sequence:
1. **Start Core Services**: `./restart_services.sh`
2. **Start Market Feed**: `python scripts/ingestion/angel_one_ws.py`
3. **Start Compute Pipeline**: 
    - `python scripts/compute/bar_builder_1s.py`
    - `python scripts/compute/bar_aggregator_1m.py`

---

## 📈 Institutional Observability

Professional-grade monitoring is built-in:
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000)
    - View: "Nifty Elite: Institutional Overview"
    - Metrics: Tick velocity, pipeline latency, tradable equity, and AI conviction.
- **Prometheus**: [http://localhost:9090](http://localhost:9090)

---

## 📂 Directory Structure

```text
├── infra/                  # Kafka, Postgres, Prometheus & Grafana configs
├── scripts/
│   ├── ingestion/          # Angel One WS -> Kafka
│   ├── compute/            # 1s/1m Bar Builders
├── services/
│   ├── ai-service/         # Gemma Thesis Engine
│   ├── signal-service/     # 7-Strategy & Ensemble Engine
│   ├── execution-service/  # Risk Manager & OMS
│   └── data-service/       # Historical & News API
├── frontend/               # Institutional Trading Dashboard
└── HEDGE_FUND_PLAN.md      # Integration Roadmap & Mottos
```

---

## 📜 Audit & Compliance
Every order generates a `client_order_id` and an `audit_hash`. All state changes (e.g., from `NEW` to `APPROVED` by Risk Manager) are logged in the `order_audit` table, ensuring 100% traceability for institutional reporting.

---
**Institutional Standard**: *Always verify AI Thesis validation status in the Signal Dashboard before manual overrides.*
