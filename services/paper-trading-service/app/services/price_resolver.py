from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

class PriceResolver:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_price(self, symbol: str) -> float:
        """
        Fetches the latest 'close' price for a symbol from ohlcv_enriched.
        Falls back to 0.0 if not found.
        """
        try:
            query = text(
                "SELECT close FROM ohlcv_enriched "
                "WHERE symbol = :symbol "
                "ORDER BY timestamp DESC LIMIT 1"
            )
            result = self.db.execute(query, {"symbol": symbol}).fetchone()
            if result:
                return float(result[0])
        except Exception as e:
            logging.error(f"Error resolving price for {symbol}: {e}")
        
        return 0.0
