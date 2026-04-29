from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from app.models.database import Base
from datetime import datetime

class StrategySignal(Base):
    __tablename__ = "strategy_signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    strategy_name = Column(String, index=True)
    direction = Column(String)  # BUY or SHORT
    entry_price = Column(Float)
    probability = Column(Float)
    expected_return = Column(Float)
    expected_drawdown = Column(Float)
    regime = Column(String)
    is_anomaly = Column(Boolean)
    backtest_id = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TradeSignal(Base):
    __tablename__ = "trade_signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    strategy_name = Column(String, index=True)
    direction = Column(String)  # BUY or SHORT
    entry = Column(Float)
    stop_loss = Column(Float)
    target_l1 = Column(Float)
    target_l2 = Column(Float)
    target_l3 = Column(Float)
    probability = Column(Float)
    confidence = Column(Float)
    regime = Column(String)
    status = Column(String, default="ALERT_PENDING_TRADER_ACTION")
    backtest_id = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class OHLCVEnriched(Base):
    __tablename__ = "ohlcv_enriched"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    
    # Core Indicators
    prev_close = Column(Float, nullable=True)
    returns = Column(Float, nullable=True)
    log_return = Column(Float, nullable=True)
    range = Column(Float, nullable=True)
    range_pct = Column(Float, nullable=True)
    
    # Volume & VWAP
    cum_vol = Column(Float, nullable=True)
    vwap = Column(Float, nullable=True)
    rolling_avg_volume = Column(Float, nullable=True)
    is_volume_spike = Column(Integer, nullable=True) # 0 or 1
    vol_5 = Column(Float, nullable=True)
    vol_15 = Column(Float, nullable=True)
    distance_from_vwap = Column(Float, nullable=True)
    
    # Intraday Context
    day_open = Column(Float, nullable=True)
    distance_from_open = Column(Float, nullable=True)
    volume_zscore = Column(Float, nullable=True)
    volume_spike_ratio = Column(Float, nullable=True)
    minutes_from_open = Column(Integer, nullable=True)
    minutes_to_close = Column(Integer, nullable=True)
    day_of_week = Column(Integer, nullable=True)
    is_monday = Column(Integer, nullable=True)
    is_friday = Column(Integer, nullable=True)
    is_expiry_day = Column(Integer, nullable=True)
    
    # Technical Indicators (aligned with ta library)
    rsi_14 = Column(Float, nullable=True)
    macd_hist = Column(Float, nullable=True)
    adx_14 = Column(Float, nullable=True)
    stoch_k_14 = Column(Float, nullable=True)
    atr_14 = Column(Float, nullable=True)
    bollinger_b = Column(Float, nullable=True)
    cmf_20 = Column(Float, nullable=True)
    
    # Advanced Stats
    volatility_20d = Column(Float, nullable=True)
    obv_slope_10 = Column(Float, nullable=True)
    rvol_20 = Column(Float, nullable=True)
    relative_strength = Column(Float, nullable=True)
    
    # Lags & Momentum
    return_lag_1 = Column(Float, nullable=True)
    return_lag_2 = Column(Float, nullable=True)
    return_5d = Column(Float, nullable=True)
    rsi_lag_1 = Column(Float, nullable=True)
    macd_hist_lag_1 = Column(Float, nullable=True)
    atr_lag_1 = Column(Float, nullable=True)
    
    # Signal Processing
    sin_dayofweek = Column(Float, nullable=True)
    cos_dayofweek = Column(Float, nullable=True)
    frac_diff_close = Column(Float, nullable=True)
    wavelet_return = Column(Float, nullable=True)
    
    # Metadata
    sector = Column(String, nullable=True)
    target = Column(Integer, nullable=True)
