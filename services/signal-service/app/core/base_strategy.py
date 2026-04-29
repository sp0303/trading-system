from abc import ABC, abstractmethod
from typing import Optional, Dict

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def update(self, symbol: str, features: dict) -> Optional[Dict]:
        """
        symbol: the stock ticker being processed.
        features: dictionary of latest OHLCV + Enriched features.
        Returns a signal dict if breakout/setup detected, else None.
        """
        pass

    @abstractmethod
    def get_diagnostics(self, symbol: str, features: dict) -> Dict:
        """
        Returns a diagnostic dictionary containing 'status' and 'note' (rationale).
        """
        pass

    def get_feature(self, features: dict, key: str, default: any = 0) -> any:
        """
        Helper to fetch features case-insensitively with special char normalization.
        Maps Bollinger_%B -> bollinger_b, etc.
        """
        # Direct match
        if key in features:
            return features[key]

        # Lowercase fallback (DB column names)
        lower_key = key.lower()
        if lower_key in features:
            return features[lower_key]

        # Normalize: remove %, replace spaces with _, strip trailing _
        # e.g. "Bollinger_%B" -> "bollinger_b"
        normalized = lower_key.replace('%', '').replace(' ', '_').strip('_')
        if normalized in features:
            return features[normalized]

        return default


    @abstractmethod
    def reset_daily(self) -> None:
        """
        MANDATORY: Called at the start of every new trading day for cleanup.
        """
        pass
