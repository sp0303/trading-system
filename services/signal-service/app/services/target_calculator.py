import logging
from typing import Dict, Any

class TargetCalculator:
    """
    Hedge Fund Level dynamic target calculation system.
    Calculates Entry, Stop Loss (SL), and 3 Profit-Booking Levels (L1, L2, L3).
    """
    def __init__(self):
        logging.info("TargetCalculator initialized.")

    def calculate(self, entry: float, direction: str, atr: float) -> Dict[str, float]:
        if atr <= 0:
            # Fallback if ATR is missing (very rare but safety first)
            atr = entry * 0.01 
            
        if direction == "BUY":
            return {
                "entry": entry,
                "stop_loss": entry - (1.0 * atr),
                "target_l1": entry + (1.0 * atr),
                "target_l2": entry + (2.0 * atr),
                "target_l3": entry + (3.5 * atr)
            }
        else: # SHORT
            return {
                "entry": entry,
                "stop_loss": entry + (1.0 * atr),
                "target_l1": entry - (1.0 * atr),
                "target_l2": entry - (2.0 * atr),
                "target_l3": entry - (3.5 * atr)
            }
