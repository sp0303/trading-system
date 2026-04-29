import logging
from typing import Optional, Dict, Any
from app.core.base_strategy import BaseStrategy


class RelativeStrengthStrategy(BaseStrategy):
    """
    Strategy 4: Relative Strength (Sector Rotation)
    Used by: Millennium Management, Point72, Balyasny.

    Longs the top-performing stock in the top-performing sector vs Nifty.
    LONG only — no shorting in this strategy.
    Active regime: Any (always enabled per README).

    Entry condition: stock's return_percentile > 85th AND volume_percentile > 70th.
    This signals the stock is leading its sector AND has institutional conviction.
    """

    MIN_MINUTES_FROM_OPEN = 30    # Need initial range to establish relative strength ranking
    RETURN_PERCENTILE_THRESHOLD = 0.85
    VOLUME_PERCENTILE_THRESHOLD = 0.70

    def __init__(self):
        super().__init__("Relative Strength")
        self._fired: Dict[str, bool] = {}
        logging.info("RelativeStrengthStrategy (Strategy 4) initialized.")

    def update(self, symbol: str, features: dict) -> Optional[Dict[str, Any]]:
        if self._fired.get(symbol, False):
            return None

        mfo = features.get("minutes_from_open", 0)
        if mfo < self.MIN_MINUTES_FROM_OPEN:
            return None  # Percentile ranks not meaningful at open

        close = features.get("close", 0)
        return_percentile = self.get_feature(features, "return_percentile")
        volume_percentile = self.get_feature(features, "volume_percentile")
        relative_strength = self.get_feature(features, "relative_strength", None)

        # Core filter: top return percentile + high volume participation
        if (
            return_percentile > self.RETURN_PERCENTILE_THRESHOLD
            and volume_percentile > self.VOLUME_PERCENTILE_THRESHOLD
        ):
            self._fired[symbol] = True
            logging.info(
                f"RELATIVE STRENGTH LONG for {symbol}: "
                f"return_pct={return_percentile:.2f}, vol_pct={volume_percentile:.2f}, "
                f"rel_strength={relative_strength}"
            )
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "BUY",  # LONG ONLY per README
                "entry_price": close,
                "timestamp": features.get("timestamp"),
            }

        return None

    def get_diagnostics(self, symbol: str, features: dict) -> Dict[str, Any]:
        return_percentile = self.get_feature(features, "return_percentile", 0) or 0.0
        rel_strength = self.get_feature(features, "relative_strength", 0) or 0.0
        
        if return_percentile > 0.8:
            status = "Leading"
            note = f"Outperforming {return_percentile*100:.0f}% of universe. Rel Strength: {rel_strength:.2f}"
        elif return_percentile < 0.2:
            status = "Lagging"
            note = f"Underperforming { (1-return_percentile)*100:.0f}% of universe. Rel Strength: {rel_strength:.2f}"
        else:
            status = "Average"
            note = f"Performing near median (Rank: {return_percentile*100:.0f}th pct). Rel Strength: {rel_strength:.2f}"
            
        return {"status": status, "note": note}

    def reset_daily(self) -> None:
        """Reset for a new trading day."""
        self._fired = {}
