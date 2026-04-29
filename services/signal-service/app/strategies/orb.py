from app.core.base_strategy import BaseStrategy
from typing import Optional, Dict, Any
import logging

class ORBStrategy(BaseStrategy):
    """
    Strategy 1: Opening Range Breakout (ORB)
    Detects breakouts above/below the first 15-minute high/low with volume confirmation.
    """
    def __init__(self):
        super().__init__("ORB")
        # Store state per symbol: { symbol: { "high": float, "low": float, "triggered": bool } }
        self.states = {}
        logging.info("ORBStrategy (Strategy 1) initialized.")

    def update(self, symbol: str, features: dict) -> Optional[Dict[str, Any]]:
            
        # Initialize state for symbol if new
        if symbol not in self.states:
            self.states[symbol] = {"high": -float('inf'), "low": float('inf'), "triggered": False}
        
        state = self.states[symbol]
        if state["triggered"]:
            return None # Already fired for today for this symbol

        mfo = features.get("minutes_from_open", 0)
        high = features.get("high", 0)
        low = features.get("low", 0)
        close = features.get("close", 0)
        
        # 1. Defining the 15-min Opening Range (9:15 - 9:30)
        if mfo <= 15:
            state["high"] = max(state["high"], high)
            state["low"] = min(state["low"], low)
            logging.debug(f"[{symbol}] range tracking: mfo={mfo} high={state['high']} low={state['low']}")
            return None
            
        # 2. Post-Opening Range: Detect Breakouts
        if state["high"] == -float('inf') or state["low"] == float('inf'):
            logging.warning(f"[{symbol}] No opening range found before mfo={mfo}")
            return None
            
        vol_spike = features.get("volume_spike_ratio", 0)
        
        # Breakdown detection logs
        if close > state["high"] or close < state["low"]:
             logging.info(f"[{symbol}] BREAKOUT ATTEMPT at {close} (High: {state['high']}, Low: {state['low']}, Vol: {vol_spike:.2f})")

        # Institutional Validation (Volume Spike > 2.0)
        if close > state["high"] and vol_spike > 2.0:
            state["triggered"] = True
            logging.info(f"ORB LONG Breakout detected for {symbol} at {close} (vol_spike: {vol_spike})")
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "BUY",
                "entry_price": close,
                "timestamp": features.get("timestamp")
            }
        elif close < state["low"] and vol_spike > 2.0:
            state["triggered"] = True
            logging.info(f"ORB SHORT Breakout detected for {symbol} at {close} (vol_spike: {vol_spike})")
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "SHORT",
                "entry_price": close,
                "timestamp": features.get("timestamp")
            }
            
        return None

    def get_diagnostics(self, symbol: str, features: dict) -> Dict[str, Any]:
        state = self.states.get(symbol, {"high": -float('inf'), "low": float('inf'), "triggered": False})
        close = features.get("close") or 0.0
        mfo = features.get("minutes_from_open") or 0

        if mfo <= 15:
            return {"status": "Monitoring", "note": "Establishing opening range..."}
        if state["triggered"]:
             return {"status": "Triggered", "note": f"Range breakout already occurred."}
        
        if state["high"] == -float('inf') or state["low"] == float('inf'):
            return {"status": "Neutral", "note": "Range calibration in progress."}

        if close > state["high"]:
            return {"status": "Bullish", "note": f"Price ₹{close:.1f} > ORB High ₹{state['high']:.1f}"}
        elif close < state["low"]:
            return {"status": "Bearish", "note": f"Price ₹{close:.1f} < ORB Low ₹{state['low']:.1f}"}
        else:
            return {"status": "Neutral", "note": "Trading within 15m opening range."}

    def reset_daily(self):
        """Reset all states for a new trading day."""
        self.states = {}
