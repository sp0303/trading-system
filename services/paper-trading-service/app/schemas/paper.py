from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class PaperOrderBase(BaseModel):
    symbol: str
    side: str
    qty: int
    requested_price: Optional[float] = None
    order_type: str = "MARKET"
    strategy_name: Optional[str] = None
    regime: Optional[str] = None
    trade_signal_id: Optional[int] = None
    source: str = "frontend"
    extra: Dict[str, Any] = {}

class PaperOrderCreate(PaperOrderBase):
    pass

class PaperOrderResponse(PaperOrderBase):
    id: int
    client_order_id: str
    status: str
    filled_qty: int
    avg_fill_price: Optional[float] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaperFillResponse(BaseModel):
    id: int
    client_order_id: str
    symbol: str
    side: str
    qty: int
    price: float
    fees: float
    timestamp: datetime

    class Config:
        from_attributes = True

class PaperPositionResponse(BaseModel):
    symbol: str
    net_qty: int
    avg_price: float
    last_price: Optional[float] = None
    realized_pnl: float
    unrealized_pnl: float
    updated_at: datetime

    class Config:
        from_attributes = True

class PaperPnlSummary(BaseModel):
    realized_pnl: float
    unrealized_pnl: float
    open_positions: int
    closed_trades: int
