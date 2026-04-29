import logging
from typing import Optional, Dict, Any
from app.core.base_strategy import BaseStrategy


class VWAPReversionStrategy(BaseStrategy):
    """
    Strategy 2: VWAP Mean Reversion
    Used by: Citadel, Virtu, IMC — institutional market makers.

    Trades when price deviates > 1.5 ATR from VWAP and shows reversal signals.
    Active regime: Range-Bound only.

    LONG  when price is significantly below VWAP + RSI oversold.
    SHORT when price is significantly above VWAP + RSI overbought.
    One signal per symbol per day.
    """

    MIN_MINUTES_FROM_OPEN = 30   # Wait for VWAP to stabilize
    RSI_OVERSOLD = 35
    RSI_OVERBOUGHT = 65
    ATR_DEVIATION_MULTIPLIER = 1.5  # Distance from VWAP must be > 1.5 ATR

    def __init__(self):
        super().__init__("VWAP Reversion")
        # { symbol: bool } — True if already fired today
        self._fired: Dict[str, bool] = {}
        logging.info("VWAPReversionStrategy (Strategy 2) initialized.")

    def update(self, symbol: str, features: dict) -> Optional[Dict[str, Any]]:
        if self._fired.get(symbol, False):
            return None  # One shot per day

        mfo = features.get("minutes_from_open", 0)
        if mfo < self.MIN_MINUTES_FROM_OPEN:
            return None  # Too early, VWAP not reliable

        close = features.get("close", 0)
        vwap = self.get_feature(features, "vwap")
        atr = self.get_feature(features, "ATR_14")
        rsi = self.get_feature(features, "RSI_14", 50.0)
        distance = self.get_feature(features, "distance_from_vwap", None)

        if not vwap or not atr or atr <= 0:
            return None

        # Compute distance if not pre-calculated
        if distance is None:
            distance = close - vwap

        threshold = self.ATR_DEVIATION_MULTIPLIER * atr

        # LONG: price far below VWAP + RSI oversold (reversion upward expected)
        if distance < -threshold and rsi < self.RSI_OVERSOLD:
            self._fired[symbol] = True
            logging.info(
                f"VWAP LONG Reversion for {symbol}: close={close:.2f}, "
                f"vwap={vwap:.2f}, dist={distance:.2f}, rsi={rsi:.1f}"
            )
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "BUY",
                "entry_price": close,
                "timestamp": features.get("timestamp"),
            }

        # SHORT: price far above VWAP + RSI overbought (reversion downward expected)
        if distance > threshold and rsi > self.RSI_OVERBOUGHT:
            self._fired[symbol] = True
            logging.info(
                f"VWAP SHORT Reversion for {symbol}: close={close:.2f}, "
                f"vwap={vwap:.2f}, dist={distance:.2f}, rsi={rsi:.1f}"
            )
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "SHORT",
                "entry_price": close,
                "timestamp": features.get("timestamp"),
            }

        return None

    def get_diagnostics(self, symbol: str, features: dict) -> Dict[str, Any]:
        close = features.get("close") or 0.0
        vwap = self.get_feature(features, "vwap")
        rsi = self.get_feature(features, "RSI_14", 50.0) or 50.0
        
        if not vwap:
            return {"status": "Neutral", "note": "VWAP data not available."}
            
        diff_pct = (close - vwap) / vwap * 100
        
        if diff_pct > 1.5 and rsi > 65:
            return {"status": "Overbought", "note": f"Price ₹{close:.1f} is {diff_pct:.1f}% above VWAP. RSI: {rsi:.1f}"}
        elif diff_pct < -1.5 and rsi < 35:
            return {"status": "Oversold", "note": f"Price ₹{close:.1f} is {abs(diff_pct):.1f}% below VWAP. RSI: {rsi:.1f}"}
        else:
            return {"status": "Neutral", "note": f"Price ₹{close:.1f} is {abs(diff_pct):.1f}% {'above' if diff_pct > 0 else 'below'} VWAP."}

    def reset_daily(self) -> None:
        """Clear all symbol fire-states for the new trading day."""
        self._fired = {}
