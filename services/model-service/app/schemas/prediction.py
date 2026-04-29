from pydantic import BaseModel
from typing import List, Optional, Dict

class FeatureInput(BaseModel):
    symbol: str
    timestamp: str
    # 70 fields total - grouping for better representation
    features: Dict[str, float]

class ModelPrediction(BaseModel):
    symbol: str
    probability: float
    expected_return: float
    expected_drawdown: float
    confidence: float
    regime: str
    is_anomaly: bool
    models_used: List[str]

class PredictionResponse(BaseModel):
    status: str
    data: Optional[ModelPrediction] = None
    error: Optional[str] = None
