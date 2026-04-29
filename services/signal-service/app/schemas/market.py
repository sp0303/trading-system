from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Candle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class SymbolInfo(BaseModel):
    symbol: str
    label: str
    sector: str
    last_price: float
    change_pct: float

class SymbolsListResponse(BaseModel):
    status: str
    data: List[SymbolInfo]
    error: Optional[str] = None

class HistoryResponse(BaseModel):
    status: str
    data: Dict[str, Any]
    error: Optional[str] = None

class BenchmarkResponse(BaseModel):
    status: str
    data: Dict[str, Any]
    error: Optional[str] = None

class StrategyInsight(BaseModel):
    name: str
    status: str
    confidence: float
    note: str
    last_signal_time: str

class InsightsResponse(BaseModel):
    status: str
    data: Dict[str, Any]
    error: Optional[str] = None
