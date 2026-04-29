-- Institutional Trading Tables (Hedge-Fund Grade)
-- Part 1: Core Execution Tables
CREATE TABLE IF NOT EXISTS orders (
  order_id         bigserial PRIMARY KEY,
  ts               timestamptz NOT NULL DEFAULT now(),
  client_order_id  text UNIQUE,
  symbol           text        NOT NULL,
  side             text        NOT NULL CHECK (side IN ('BUY','SELL')),
  qty              integer     NOT NULL CHECK (qty > 0),
  order_type       text        NOT NULL DEFAULT 'MKT',
  limit_price      double precision,
  strategy         text        NOT NULL,
  reason           text,
  risk_bucket      text,
  status           text        NOT NULL DEFAULT 'NEW',
  extra            jsonb       NOT NULL DEFAULT '{}'::jsonb,
  last_update      timestamptz NOT NULL DEFAULT now(),
  audit_hash       text
);

CREATE INDEX IF NOT EXISTS orders_status_idx ON orders(status);
CREATE INDEX IF NOT EXISTS orders_symbol_idx ON orders(symbol);
CREATE INDEX IF NOT EXISTS orders_ts_idx     ON orders(ts);

CREATE TABLE IF NOT EXISTS fills (
  fill_id    bigserial PRIMARY KEY,
  order_id   bigint       NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  ts         timestamptz  NOT NULL DEFAULT now(),
  qty        integer      NOT NULL CHECK (qty > 0),
  price      double precision NOT NULL,
  venue      text,
  extra      jsonb        NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS fills_order_idx ON fills(order_id);
CREATE INDEX IF NOT EXISTS fills_ts_idx    ON fills(ts);

-- Part 2: Audit & Traceability
CREATE TABLE IF NOT EXISTS order_audit (
  id      bigserial PRIMARY KEY,
  client_order_id text NOT NULL,
  ts      timestamptz NOT NULL DEFAULT now(),
  from_st text,
  to_st   text,
  note    text,
  meta    jsonb
);

CREATE INDEX IF NOT EXISTS order_audit_coid_idx ON order_audit(client_order_id);

-- Part 3: Aggregated Views (Blotter)
CREATE OR REPLACE VIEW institutional_blotter AS
SELECT
  o.order_id, o.ts AS order_ts, o.client_order_id, o.symbol, o.side, o.qty AS ord_qty,
  o.order_type, o.limit_price, o.strategy, o.reason, o.risk_bucket, o.status,
  COALESCE(SUM(f.qty), 0)           AS fill_qty,
  CASE WHEN COALESCE(SUM(f.qty),0) > 0
       THEN SUM(f.qty * f.price)::double precision / SUM(f.qty)
       ELSE NULL
  END                               AS avg_fill_price,
  MAX(f.ts)                         AS last_fill_ts
FROM orders o
LEFT JOIN fills f ON f.order_id = o.order_id
GROUP BY o.order_id;
