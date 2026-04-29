import logging
from typing import Optional, Dict, Any
from app.core.base_strategy import BaseStrategy


class IntradayMomentumStrategy(BaseStrategy):
    """
    Strategy 3: Intraday Momentum
    Used by: Two Sigma, DE Shaw — systematic momentum programs.

    Identifies continuation moves when RSI, MACD, and price action align.
    Enters in direction of the established intraday trend.
    Active regime: Trending, Normal.

    LONG  when MACD_Hist > 0 + RSI > 55 + ADX > 20 + positive return lag.
    SHORT when MACD_Hist < 0 + RSI < 45 + ADX > 20 + negative return lag.
    One signal per symbol per day (strongest-conviction window).
    """

    MIN_MINUTES_FROM_OPEN = 30  # Wait for trend to establish
    ADX_TREND_THRESHOLD = 20
    RSI_BULL_THRESHOLD = 55
    RSI_BEAR_THRESHOLD = 45

    def __init__(self):
        super().__init__("Momentum")
        self._fired: Dict[str, bool] = {}
        logging.info("IntradayMomentumStrategy (Strategy 3) initialized.")

    def update(self, symbol: str, features: dict) -> Optional[Dict[str, Any]]:
        if self._fired.get(symbol, False):
            return None

        mfo = features.get("minutes_from_open", 0)
        if mfo < self.MIN_MINUTES_FROM_OPEN:
            return None  # Need 30 min for trend confirmation

        close = features.get("close", 0)
        macd_hist = self.get_feature(features, "MACD_Hist")
        rsi = self.get_feature(features, "RSI_14", 50.0)
        adx = self.get_feature(features, "ADX_14")
        return_lag = self.get_feature(features, "Return_Lag_1")

        if adx < self.ADX_TREND_THRESHOLD:
            return None  # No trend — skip

        # LONG: All momentum indicators align bullish
        if macd_hist > 0 and rsi > self.RSI_BULL_THRESHOLD and return_lag > 0:
            self._fired[symbol] = True
            logging.info(
                f"MOMENTUM LONG for {symbol}: macd_hist={macd_hist:.4f}, "
                f"rsi={rsi:.1f}, adx={adx:.1f}, ret_lag={return_lag:.4f}"
            )
            return {
                "symbol": symbol,
                "strategy_name": self.name,
                "direction": "BUY",
                "entry_price": close,
                "timestamp": features.get("timestamp"),
            }

        # SHORT: All momentum indicators align bearish
        if macd_hist < 0 and rsi < self.RSI_BEAR_THRESHOLD and return_lag < 0:
            self._fired[symbol] = True
            logging.info(
                f"MOMENTUM SHORT for {symbol}: macd_hist={macd_hist:.4f}, "
                f"rsi={rsi:.1f}, adx={adx:.1f}, ret_lag={return_lag:.4f}"
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
        rsi = self.get_feature(features, "RSI_14", 50.0) or 50.0
        adx = self.get_feature(features, "ADX_14", 0) or 0.0
        macd_hist = self.get_feature(features, "MACD_Hist", 0) or 0.0
        
        if adx > 25:
            trend = "Strong"
        elif adx > 20:
            trend = "Moderate"
        else:
            trend = "Weak/No"
            
        if macd_hist > 0 and rsi > 55:
            sentiment = "Bullish Momentum"
        elif macd_hist < 0 and rsi < 45:
            sentiment = "Bearish Momentum"
        else:
            sentiment = "Neutral"
            
        return {"status": sentiment, "note": f"{trend} trend (ADX: {adx:.1f}). MACD Hist: {macd_hist:.3f}, RSI: {rsi:.1f}"}

    def reset_daily(self) -> None:
        """Reset for a new trading day."""
        self._fired = {}
