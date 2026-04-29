from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ProcessData(BaseModel):
    symbol: str
    timestamp: str
    features: Dict[str, Any]
    backtest_id: Optional[str] = None

class SignalResponse(BaseModel):
    id: int
    symbol: str
    strategy: str
    direction: str
    entry: float
    stop_loss: float
    target_l1: float
    target_l2: float
    target_l3: float
    probability: float
    confidence: float
    regime: str
    timestamp: str
    status: str

class SignalsListResponse(BaseModel):
    status: str
    data: List[SignalResponse]
    error: Optional[str] = None
