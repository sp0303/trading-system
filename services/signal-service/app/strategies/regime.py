import logging

class MarketRegimeClassifier:
    """
    Strategy 7: Market Regime Classifier (Meta-Strategy)
    Determines if the market is Trending, Range-Bound, or Volatile.
    """
    def __init__(self):
        logging.info("MarketRegimeClassifier (Strategy 7) initialized.")

    def classify(self, features: dict) -> str:
        adx = features.get("ADX_14") or features.get("adx_14", 0)
        
        # Logic from README line 170
        if adx > 25:
            return "Trending"
        elif adx < 20:
            return "Range-Bound"
        
        # Fallback to Normal
        return "Normal"

    def get_diagnostics(self, features: dict) -> dict:
        adx = features.get("ADX_14") or features.get("adx_14") or 0.0
        regime = self.classify(features)
        
        note = f"Market is {regime} (ADX: {adx:.1f}). "
        if regime == "Trending":
            note += "Strong directional conviction."
        elif regime == "Range-Bound":
            note += "Price compressing, favoring reversion."
        else:
            note += "Stable market conditions."
            
        return {"status": regime, "note": note}

    def is_strategy_allowed(self, strategy_name: str, regime: str) -> bool:
        """
        Policy engine (README line 170).
        """
        policies = {
            "Trending": ["ORB", "Momentum", "Relative Strength"],
            "Range-Bound": ["VWAP Reversion", "Volume Reversal", "Relative Strength"],
            "Normal": ["ORB", "Momentum", "VWAP Reversion", "Relative Strength"] # Normal allows most common
        }
        
        allowed = policies.get(regime, [])
        return strategy_name in allowed
