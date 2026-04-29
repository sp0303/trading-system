# Hedge-Fund Integration: Nifty Elite x Sentinel Stack
**Motto**: *"Intelligence-Driven, Infrastructure-Hardened Execution."*

### Final End Goal
A unified, institutional-grade trading platform that combines **Gemma-powered AI reasoning** with **Kafka-driven 1ms data throughput**, monitored by a professional **Prometheus/Grafana** observability suite.

---

## Phase 1: Infrastructure Initialization (The Backbone)
We must first build the engine room before we can run the logic.
1.  **Infrastructure Deployment**: 
    - Install and configure **Apache Kafka** & **Zookeeper** (using Docker for clean isolation).
    - Deploy **Redis** for hot-state caching (Strategy regimes and real-time metrics).
2.  **Database Migration**:
    - Update our Postgres schema to support their `orders` and `order_audit` tables for full lifecycle traceability.

## Phase 2: High-Performance Data Migration (The Senses)
Moving from request-based polling to stream-based processing.
1.  **Ingestion Port**: Bring in `trading-platform-main/ingestion/` to support Zerodha/AngelOne multi-broker ticks.
2.  **Compute Port**: Migrate the **Go/Python Bar Builder** (1s -> 1m -> Multi-TF). 
3.  **The Gold Standard**: Ensure the data from their bar builder flows directly into our `ohlcv_enriched` schema.

## Phase 3: Risk & Execution Consolidation (The Guardrails)
Replacing simple paper trading with a professional Order Management System.
1.  **Risk Manager Migration**: Import `risk/manager_v2.py` as a mandatory middleware for every trade request.
2.  **Idempotent OMS**: Replace our HTTP-based execution logic with their **OMS router**. 
    - *Every trade will now have a Client Order ID, Audit Hash, and full State Transition history.*

## Phase 4: The Intelligence Loop (The Brain)
Wiring our AI to the new high-performance hardware.
1.  **Signal Re-wiring**: Update the `signal-service` to consume Kafka "Gold Bars" instead of querying Postgres.
2.  **AI Validation Hook**: Configure the AI Service (Gemma) as a "Soft-Block" in the execution pipeline. 
    - *Signal -> AI Approval -> Risk Check -> OMS Execution.*

## Phase 5: Institutional Observability (The Dashboard)
Moving from console logs to professional monitoring.
1.  **Metrics Exporters**: Integrate their Prometheus exporters into all services (Signal, AI, News).
2.  **Grafana Setup**: Deploy their canonical Dashboards to visualize:
    - Order fill rates and latencies.
    - AI Conviction distribution.
    - Broker connectivity status.

---

## Implementation Status Tracking
- [ ] Phase 1: Kafka & Redis Setup
- [ ] Phase 2: Go/Python Bar Builder Migration
- [ ] Phase 3: Risk Manager & OMS Integration
- [ ] Phase 4: AI & Signal Service Wiring
- [ ] Phase 5: Prometheus/Grafana Deployment
