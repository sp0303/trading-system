import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.schema import OHLCVEnriched
from datetime import datetime, timedelta
from typing import List, Optional

class MarketDataService:
    def __init__(self, db: Session):
        self.db = db

    def get_symbols(self):
        """Fetch unique symbols and their latest price info."""
        # This is a bit heavy without a dedicated symbols table. 
        # For now, we take unique symbols and their latest close from the most recent timestamp.
        
        # Subquery to find the latest timestamp for each symbol
        latest_ts_subquery = self.db.query(
            OHLCVEnriched.symbol,
            func.max(OHLCVEnriched.timestamp).label("max_ts")
        ).group_by(OHLCVEnriched.symbol).subquery()

        # Join with main table to get the latest close and sector
        results = self.db.query(
            OHLCVEnriched.symbol,
            OHLCVEnriched.close,
            OHLCVEnriched.timestamp,
            OHLCVEnriched.sector,
            OHLCVEnriched.returns
        ).join(
            latest_ts_subquery,
            (OHLCVEnriched.symbol == latest_ts_subquery.c.symbol) &
            (OHLCVEnriched.timestamp == latest_ts_subquery.c.max_ts)
        ).all()

        return [
            {
                "symbol": r.symbol,
                "label": r.symbol,
                "last_price": r.close,
                "change_pct": round(r.returns, 2) if r.returns else 0.0,
                "sector": r.sector or "Other"
            }
            for r in results
        ]

    def get_history(self, symbol: str, time_range: str = "1D", limit: Optional[int] = None):
        """Fetch OHLC history for a symbol based on time range."""
        query = self.db.query(OHLCVEnriched).filter(OHLCVEnriched.symbol == symbol)
        
        # Optimization: Fetch global "now" for this symbol specifically to avoid full index scan
        # If not found for symbol, then fallback to global max (riskier but better than utcnow baseline)
        now = self.db.query(func.max(OHLCVEnriched.timestamp)).filter(OHLCVEnriched.symbol == symbol).scalar()
        if not now:
            now = self.db.query(func.max(OHLCVEnriched.timestamp)).scalar() or datetime.utcnow()
        
        if time_range == "1D":
            # Last trading day (intraday 1m)
            # Find the start of the last day available
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(OHLCVEnriched.timestamp >= start_date)
            
            if limit:
                # Fetch last N records for performance
                query = query.order_by(OHLCVEnriched.timestamp.desc()).limit(limit)
                results = query.all()
                results = list(reversed(results))
                return self._format_results(results)
            
            query = query.order_by(OHLCVEnriched.timestamp.asc())
        elif time_range == "1M":
            # Last 30 days
            start_date = now - timedelta(days=30)
            query = query.filter(OHLCVEnriched.timestamp >= start_date)
            query = query.order_by(OHLCVEnriched.timestamp.asc()).limit(15000)
        elif time_range == "1Y":
            # Last 365 days
            start_date = now - timedelta(days=365)
            query = query.filter(OHLCVEnriched.timestamp >= start_date)
            query = query.order_by(OHLCVEnriched.timestamp.asc()).limit(30000)
        else:
            query = query.order_by(OHLCVEnriched.timestamp.desc()).limit(1000)

        results = query.all()
        if time_range not in {"1D", "1M", "1Y"}:
            results = list(reversed(results))

        return self._format_results(results)

    def _format_results(self, results):
        """
        Format DB rows into chart-ready dicts.
        Includes all enriched technical features for the frontend.
        """
        output = []
        for r in results:
            point = {
                # Core OHLCV (required by TradingView chart)
                "time": int(r.timestamp.timestamp()),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                # Enriched Technical Indicators
                "rsi_14": round(r.rsi_14, 2) if r.rsi_14 else None,
                "macd_hist": round(r.macd_hist, 4) if r.macd_hist else None,
                "adx_14": round(r.adx_14, 2) if r.adx_14 else None,
                "atr_14": round(r.atr_14, 4) if r.atr_14 else None,
                "stoch_k_14": round(r.stoch_k_14, 2) if r.stoch_k_14 else None,
                "bollinger_b": round(r.bollinger_b, 3) if r.bollinger_b else None,
                "cmf_20": round(r.cmf_20, 3) if r.cmf_20 else None,
                # VWAP & Volume
                "vwap": round(r.vwap, 2) if r.vwap else None,
                "distance_from_vwap": round(r.distance_from_vwap, 3) if r.distance_from_vwap else None,
                "volume_spike_ratio": round(r.volume_spike_ratio, 2) if r.volume_spike_ratio else None,
                "is_volume_spike": r.is_volume_spike,
                "rvol_20": round(r.rvol_20, 2) if r.rvol_20 else None,
                # Price context
                "vwap": round(r.vwap, 2) if r.vwap else None,
                "day_open": r.day_open,
                "distance_from_open": round(r.distance_from_open, 3) if r.distance_from_open else None,
                "returns": round(r.returns, 4) if r.returns else None,
                "relative_strength": round(r.relative_strength, 3) if r.relative_strength else None,
                "volatility_20d": round(r.volatility_20d, 4) if r.volatility_20d else None,
                "obv_slope_10": round(r.obv_slope_10, 2) if r.obv_slope_10 else None,
                # Metadata
                "minutes_from_open": r.minutes_from_open,
                "sector": r.sector,
            }
            output.append(point)
        return output


    def get_benchmark(self, time_range: str = "1D", limit: Optional[int] = None):
        """Fetch real NIFTY 50 benchmark data."""
        symbol = "NIFTY50"
        
        # 1. Fetch history for the chart (possibly limited)
        history = self.get_history(symbol, time_range, limit=limit)
        if not history:
            # Fallback to RELIANCE only if NIFTY50 is completely missing
            symbol = "RELIANCE"
            history = self.get_history(symbol, time_range, limit=limit)
            if not history: return None
            
        last_item = history[-1]
        
        # 2. Calculate day change correctly
        if time_range == "1D":
            # Find today's open price
            now = self.db.query(func.max(OHLCVEnriched.timestamp)).filter(OHLCVEnriched.symbol == symbol).scalar()
            if now:
                start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                first_candle = self.db.query(OHLCVEnriched).filter(
                    (OHLCVEnriched.symbol == symbol) & 
                    (OHLCVEnriched.timestamp >= start_of_day)
                ).order_by(OHLCVEnriched.timestamp.asc()).first()
                
                if first_candle:
                    day_open = first_candle.open
                    change_pct = ((last_item["close"] - day_open) / day_open) * 100
                else:
                    change_pct = 0.0
            else:
                change_pct = 0.0
        else:
            # For 1M/1Y, use the first item in the fetched history
            first_item = history[0]
            change_pct = ((last_item["close"] - first_item["open"]) / first_item["open"]) * 100 if first_item["open"] else 0.0
            
        status = "Bullish" if change_pct > 0.5 else "Weak" if change_pct < -0.5 else "Neutral"

        return {
            "symbol": "NIFTY50",
            "label": "NIFTY 50 Index",
            "last_price": last_item["close"],
            "change_pct": round(change_pct, 2),
            "volume": last_item["volume"],
            "status": status,
            "is_proxy": symbol == "RELIANCE",
            "source_status": "live" if symbol == "NIFTY50" else "proxy",
            "breadth": {
                "advancers": 32, # Mock for now
                "decliners": 18,
                "note": "NSE Cash Market Breadth"
            },
            "series": history
        }
