import logging
import os
from typing import Dict, Any, Optional

class SignalFilter:
    """
    The Signal Filter (README line 214).
    A strict gatekeeper that ensures only high-probability, high-R:R setups reach the trader.
    """
    def __init__(self, prob_threshold: float = None, mfe_threshold: float = 0.0, mae_threshold: float = 100.0):
        # Allow override via env var for paper trading / testing
        if prob_threshold is None:
            prob_threshold = float(os.getenv("SIGNAL_PROB_THRESHOLD", "0.0"))
        self.prob_threshold = prob_threshold
        self.mfe_threshold = mfe_threshold
        self.mae_threshold = mae_threshold
        logging.info(f"SignalFilter initialized (Prob > {prob_threshold}, MFE > {mfe_threshold}, MAE < {mae_threshold})")

    def filter(self, prediction: Dict[str, Any], allowed_strategies: list, strategy_name: str) -> bool:
        """
        Returns True if the signal passes all strict statistical and risk filters.
        """
        prob = prediction.get("probability", 0)
        mfe = prediction.get("expected_return", 0)
        mae = prediction.get("expected_drawdown", 0)
        is_anomaly = prediction.get("is_anomaly", False)
        regime = prediction.get("regime", "Unknown")

        # 1. Statistical Probability Filter
        if prob < self.prob_threshold:
            logging.debug(f"Filter FAILED: low probability ({prob:.2f} < threshold {self.prob_threshold:.2f})")
            return False

        # 2. Risk/Reward (MFE/MAE) Filter
        if mfe < self.mfe_threshold or mae > self.mae_threshold:
            logging.debug(f"Filter FAILED: poor R:R (MFE: {mfe:.2f}, MAE: {mae:.2f})")
            return False

        # 3. Anomaly Detection Filter
        if is_anomaly:
            logging.debug("Filter FAILED: market anomaly detected")
            return False

        # 4. Regime-Strategy Compatibility Filter
        if strategy_name not in allowed_strategies:
            logging.debug(f"Filter FAILED: {strategy_name} not allowed in {regime} regime")
            return False

        logging.info(f"Filter PASSED for {strategy_name} (Prob: {prob:.2f}, MFE: {mfe:.2f}R)")
        return True
