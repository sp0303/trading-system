import time
import random
from typing import Dict, Any

class FillSimulator:
    def __init__(self, slippage_bps: float = 5.0, latency_ms: int = 100):
        self.slippage_bps = slippage_bps
        self.latency_ms = latency_ms

    def simulate_fill(self, symbol: str, side: str, qty: int, market_price: float) -> Dict[str, Any]:
        """
        Simulates a market fill with slippage and latency.
        """
        # 1. Simulate network/execution latency
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000.0)

        # 2. Apply slippage
        # slippage_factor = 1 + (bps / 10000) for BUY, 1 - (bps / 10000) for SELL
        slippage_amount = market_price * (self.slippage_bps / 10000.0)
        
        if side.upper() in ("BUY", "LONG"):
            fill_price = market_price + slippage_amount
        else:  # SELL or SHORT
            fill_price = market_price - slippage_amount

        turnover = fill_price * qty
        fees = round(turnover * 0.0005, 2)

        return {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": round(fill_price, 2),
            "slippage_bps": self.slippage_bps,
            "fees": fees,
            "venue": "PAPER"
        }
