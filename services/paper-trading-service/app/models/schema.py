from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Date
from sqlalchemy.sql import func
from .database import Base

class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id = Column(Integer, primary_key=True, index=True)
    client_order_id = Column(String(100), unique=True, index=True, nullable=False)
    trade_signal_id = Column(Integer, nullable=True)
    parent_client_order_id = Column(String(100), nullable=True)
    symbol = Column(String(30), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    qty = Column(Integer, nullable=False)
    requested_price = Column(Float, nullable=True)
    filled_qty = Column(Integer, default=0, nullable=False)
    avg_fill_price = Column(Float, nullable=True)
    order_type = Column(String(20), default="MARKET", nullable=False)
    strategy_name = Column(String(100), nullable=True)
    regime = Column(String(50), nullable=True)
    source = Column(String(30), default="frontend", nullable=False)
    status = Column(String(30), nullable=False, index=True)
    note = Column(String, nullable=True)
    extra = Column(JSON, default={}, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PaperOrderAudit(Base):
    __tablename__ = "paper_order_audit"

    id = Column(Integer, primary_key=True, index=True)
    client_order_id = Column(String(100), nullable=False, index=True)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    note = Column(String, nullable=True)
    meta = Column(JSON, default={}, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PaperFill(Base):
    __tablename__ = "paper_fills"

    id = Column(Integer, primary_key=True, index=True)
    client_order_id = Column(String(100), nullable=False, index=True)
    symbol = Column(String(30), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    qty = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    fees = Column(Float, default=0, nullable=False)
    slippage_bps = Column(Float, default=0, nullable=False)
    venue = Column(String(20), default="PAPER", nullable=False)
    extra = Column(JSON, default={}, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30), unique=True, nullable=False, index=True)
    net_qty = Column(Integer, default=0, nullable=False)
    avg_price = Column(Float, default=0, nullable=False)
    realized_pnl = Column(Float, default=0, nullable=False)
    last_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PaperDailyPnL(Base):
    __tablename__ = "paper_daily_pnl"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30), nullable=False, index=True)
    trading_date = Column(Date, nullable=False)
    realized_pnl = Column(Float, default=0, nullable=False)
    unrealized_pnl = Column(Float, default=0, nullable=False)
    mtm_price = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, index=True)
    total_capital = Column(Float, default=10000000.0, nullable=False) # 1 Cr Default
    available_cash = Column(Float, default=10000000.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
