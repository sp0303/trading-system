import logging
from typing import Optional, Dict, Any, Deque
from collections import deque
from app.core.base_strategy import BaseStrategy


class VolatilitySqueezeStrategy(BaseStrategy):
    """
    Strategy 5: Volatility Squeeze Breakout
    Used by: Renaissance Technologies, AQR.

    Detects Bollinger Band compression (low volatility) before an explosive move.
    Enters on the first break of the squeeze in the direction of breakout.

    LONG  if Bollinger_%B breaks above 0.6 after compression (BB squeeze).
    SHORT if Bollinger_%B breaks below 0.4 after compression.
    Active regime: Normal (Breakout Ready maps to Normal in current classifier).
    One signal per symbol per day.
    """

    # A "squeeze" = Bollinger_%B is between 0.4 and 0.6
    SQUEEZE_LOW = 0.4
    SQUEEZE_HIGH = 0.6
    BREAKOUT_HIGH = 0.65    # Break above this after squeeze → LONG
    BREAKOUT_LOW = 0.35     # Break below this after squeeze → SHORT
    MIN_SQUEEZE_BARS = 3    # Need 3 consecutive compressed bars before firing
    MIN_MINUTES_FROM_OPEN = 30

    def __init__(self):
        super().__init__("Vol Squeeze")
        self._fired: Dict[str, bool] = {}
        # Track last N Bollinger_%B values per symbol to detect compression window
        self._bb_history: Dict[str, Deque[float]] = {}
        logging.info("VolatilitySqueezeStrategy (Strategy 5) initialized.")

    def update(self, symbol: str, features: dict) -> Optional[Dict[str, Any]]:
        if self._fired.get(symbol, False):
            return None

        mfo = features.get("minutes_from_open", 0)
        if mfo < self.MIN_MINUTES_FROM_OPEN:
            return None

        bb_pct_b = self.get_feature(features, "Bollinger_%B", None)
        close = features.get("close", 0)

        if bb_pct_b is None:
            return None

        # Initialize history deque for this symbol
        if symbol not in self._bb_history:
            self._bb_history[symbol] = deque(maxlen=self.MIN_SQUEEZE_BARS + 1)

        history = self._bb_history[symbol]
        history.append(bb_pct_b)

        # Need enough history to detect squeeze
        if len(history) < self.MIN_SQUEEZE_BARS + 1:
            return None

        # Check if the N-1 bars prior were in squeeze range
        prior_bars = list(history)[:-1]
        was_squeezed = all(
            self.SQUEEZE_LOW <= b <= self.SQUEEZE_HIGH for b in prior_bars
        )

        if not was_squeezed:
            return None  # No compression period detected

        # Current bar is the potential breakout bar
        current = history[-1]

        if current > self.BREAKOUT_HIGH:
            self._fired[symbol] = True
            logging.info(
                f"VOL SQUEEZE LONG for {symbol}: bb_pct_b={current:.3f} "
                f"(after {self.MIN_SQUEEZE_BARS} squeeze bars)"
            )
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "BUY",
                "entry_price": close,
                "timestamp": features.get("timestamp"),
            }

        if current < self.BREAKOUT_LOW:
            self._fired[symbol] = True
            logging.info(
                f"VOL SQUEEZE SHORT for {symbol}: bb_pct_b={current:.3f} "
                f"(after {self.MIN_SQUEEZE_BARS} squeeze bars)"
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
        bb_pct_b = self.get_feature(features, "Bollinger_%B", 0.5) or 0.5
        
        if 0.4 <= bb_pct_b <= 0.6:
            status = "Squeezing"
            note = f"Volatility compression detected (BB %B: {bb_pct_b:.2f}). Ready for breakout."
        elif bb_pct_b > 0.65:
            status = "Expansion UP"
            note = f"Breaking out to the upside (BB %B: {bb_pct_b:.2f})."
        elif bb_pct_b < 0.35:
            status = "Expansion DOWN"
            note = f"Breaking out to the downside (BB %B: {bb_pct_b:.2f})."
        else:
            status = "Neutral"
            note = f"Volatility is stable (BB %B: {bb_pct_b:.2f})."
            
        return {"status": status, "note": note}

    def reset_daily(self) -> None:
        """Reset all per-symbol state for the new trading day."""
        self._fired = {}
        self._bb_history = {}
