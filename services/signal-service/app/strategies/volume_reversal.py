import logging
from typing import Optional, Dict, Any
from app.core.base_strategy import BaseStrategy


class VolumeSpikeReversalStrategy(BaseStrategy):
    """
    Strategy 6: Volume Spike Reversal (Exhaustion Move)
    Used by: Jane Street, Susquehanna International Group.

    Fades exhaustion moves after massive volume spikes on extended candles.
    Counter-trend — fades extreme moves in EITHER direction.

    LONG  fade: after massive down candle + volume spike + RSI oversold.
    SHORT fade: after massive up candle  + volume spike + RSI overbought.
    Active regime: Range-Bound only (fading only works when no strong trend).
    One signal per symbol per day.
    """

    VOLUME_SPIKE_THRESHOLD = 4.0   # volume_spike_ratio must be 4x+ normal
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    MIN_MINUTES_FROM_OPEN = 45    # Need market to be running before fading exhaustion
    RANGE_PCT_MULTIPLIER = 1.5    # Extended candle: range_pct must be > 1.5x ATR/close

    def __init__(self):
        super().__init__("Volume Reversal")
        self._fired: Dict[str, bool] = {}
        logging.info("VolumeSpikeReversalStrategy (Strategy 6) initialized.")

    def update(self, symbol: str, features: dict) -> Optional[Dict[str, Any]]:
        if self._fired.get(symbol, False):
            return None

        mfo = features.get("minutes_from_open", 0)
        if mfo < self.MIN_MINUTES_FROM_OPEN:
            return None

        close = features.get("close", 0)
        vol_spike = self.get_feature(features, "volume_spike_ratio")
        rsi = self.get_feature(features, "RSI_14", 50.0)
        range_pct = self.get_feature(features, "range_pct")
        atr = self.get_feature(features, "ATR_14", 0.01)
        open_price = features.get("open", close)
        timestamp = features.get("timestamp")

        if vol_spike < self.VOLUME_SPIKE_THRESHOLD:
            return None  # Not an exhaustion event

        # Check for extended candle: range_pct relative to ATR
        if close > 0:
            atr_pct = atr / close
            if range_pct < self.RANGE_PCT_MULTIPLIER * atr_pct:
                return None  # Small candle — not an exhaustion bar

        # Determine candle direction
        is_down_candle = close < open_price
        is_up_candle = close > open_price

        # LONG fade: massive down candle + huge volume + RSI oversold
        if is_down_candle and rsi < self.RSI_OVERSOLD:
            self._fired[symbol] = True
            logging.info(
                f"VOL REVERSAL LONG fade for {symbol}: "
                f"vol_spike={vol_spike:.1f}x, rsi={rsi:.1f}, range_pct={range_pct:.4f}"
            )
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "BUY",
                "entry_price": close,
                "timestamp": features.get("timestamp"),
                # Tighter SL for counter-trend: signal_filter will validate via MAE
            }

        # SHORT fade: massive up candle + huge volume + RSI overbought
        if is_up_candle and rsi > self.RSI_OVERBOUGHT:
            self._fired[symbol] = True
            logging.info(
                f"VOL REVERSAL SHORT fade for {symbol}: "
                f"vol_spike={vol_spike:.1f}x, rsi={rsi:.1f}, range_pct={range_pct:.4f}"
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
        vol_spike = self.get_feature(features, "volume_spike_ratio", 0) or 0.0
        rsi = self.get_feature(features, "RSI_14", 50.0) or 50.0
        
        if vol_spike > self.VOLUME_SPIKE_THRESHOLD:
            status = "Exhaustion"
            note = f"Massive volume spike ({vol_spike:.1f}x) detected. Watch for reversal. RSI: {rsi:.1f}"
        elif vol_spike > 2.0:
            status = "High Volume"
            note = f"Increased institutional activity ({vol_spike:.1f}x spike). RSI: {rsi:.1f}"
        else:
            status = "Normal"
            note = f"Volume is normal ({vol_spike:.1f}x). RSI: {rsi:.1f}"
            
        return {"status": status, "note": note}

    def reset_daily(self) -> None:
        """Reset for a new trading day."""
        self._fired = {}
