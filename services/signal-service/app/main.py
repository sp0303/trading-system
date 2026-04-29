import logging
import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import Float
from sqlalchemy.orm import Session
from typing import List, Optional
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.models.database import get_db
from app.models.schema import StrategySignal, TradeSignal
from app.schemas.signal import ProcessData, SignalResponse, SignalsListResponse
from app.schemas.market import SymbolsListResponse, HistoryResponse, BenchmarkResponse, InsightsResponse
from app.strategies.regime import MarketRegimeClassifier
from app.strategies.orb import ORBStrategy
from app.strategies.vwap_reversion import VWAPReversionStrategy
from app.strategies.momentum import IntradayMomentumStrategy
from app.strategies.relative_strength import RelativeStrengthStrategy
from app.strategies.volatility_squeeze import VolatilitySqueezeStrategy
from app.strategies.volume_reversal import VolumeSpikeReversalStrategy
from app.services.model_client import ModelServiceClient
from app.services.order_client import KafkaOrderClient
from app.services.ai_client import AIValidationClient
from app.services.signal_filter import SignalFilter
from app.services.target_calculator import TargetCalculator
from app.services.market_data import MarketDataService
from app.models.database import get_db, engine
from app.models.schema import Base, StrategySignal, TradeSignal, OHLCVEnriched

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

# Configure Logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Starting Kafka Order Client...")
    await paper_client.start()
    yield
    # Shutdown
    logging.info("Stopping Kafka Order Client...")
    await paper_client.stop()

app = FastAPI(title="Nifty 500 Signal Service — 7-Strategy Engine", lifespan=lifespan)

# --- Monitoring ---
REQUEST_COUNT = Counter("signal_service_requests_total", "Total requests", ["method", "endpoint"])
REQUEST_LATENCY = Histogram("signal_service_request_latency_seconds", "Request latency", ["endpoint"])

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ── Global Strategy Instances (live service — shared across requests) ──────────
regime_classifier = MarketRegimeClassifier()
strategies = [
    ORBStrategy(),
    VWAPReversionStrategy(),
    IntradayMomentumStrategy(),
    RelativeStrengthStrategy(),
    VolatilitySqueezeStrategy(),
    VolumeSpikeReversalStrategy(),
]
model_client = ModelServiceClient(base_url=os.getenv("MODEL_SERVICE_URL", "http://model-service:7003"))
signal_filter = SignalFilter()
target_calculator = TargetCalculator()
paper_client = KafkaOrderClient()
ai_validator = AIValidationClient(base_url=os.getenv("AI_SERVICE_URL", "http://ai-service:7011"))
AI_VALIDATION_ENABLED = os.getenv("AI_VALIDATION_ENABLED", "false").lower() == "true"
AUTO_PAPER_TRADING_ENABLED = os.getenv("AUTO_PAPER_TRADING_ENABLED", "false").lower() == "true"
AUTO_PAPER_TRADING_QTY = int(os.getenv("AUTO_PAPER_TRADING_QTY", "1"))

# Regime → allowed strategy names (mirrors README table exactly)
REGIME_POLICY = {
    "Trending":    ["ORB", "Momentum", "Relative Strength"],
    "Range-Bound": ["VWAP Reversion", "Volume Reversal", "Relative Strength"],
    "Normal":      ["ORB", "Momentum", "VWAP Reversion", "Vol Squeeze", "Relative Strength"],
}


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "signal-service",
        "active_strategies": [s.name for s in strategies],
    }


def is_market_open() -> bool:
    """Checks if current IST time is within NSE market hours (09:15 - 15:30)."""
    import datetime
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    # Weekends
    if now.weekday() >= 5: return False
    
    # Market Hours (09:15 to 15:20 - stop 10 mins early for safety)
    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end = now.replace(hour=15, minute=20, second=0, microsecond=0)
    return start <= now <= end


@app.post("/reset_day")
def reset_day():
    """
    MUST be called at the start of each trading day (9:15 AM).
    Resets all strategy intraday states so there is no bleed from prior day.
    """
    for strategy in strategies:
        strategy.reset_daily()
    logging.info("🌅 All strategies reset for new trading day.")
    return {"status": "ok", "message": "All strategy states reset for new day."}


@app.post("/process")
async def process_data(data: ProcessData, db: Session = Depends(get_db)):
    """
    Full 7-Strategy Pipeline:
    Data → Regime → [6 Strategies] → Ensemble → Filter → Targets → Trader Alert
    """
    if not is_market_open():
        return {"status": "market_closed", "symbol": data.symbol, "note": "Processing restricted outside market hours (09:15-15:20 IST)"}
        
    symbol = data.symbol
    features = data.features
    timestamp = data.timestamp
    backtest_id = data.backtest_id

    # 1. Classify Market Regime (Strategy 7 — Meta-Strategy)
    logging.debug(f"Processing {symbol} at {timestamp} (MFO: {features.get('minutes_from_open')})")
    regime = regime_classifier.classify(features)
    allowed = REGIME_POLICY.get(regime, ["ORB", "Momentum"])

    generated_alerts = []

    # 2. Run all 6 strategies; only use those allowed in current regime
    for strategy in strategies:
        if strategy.name not in allowed:
            continue

        signal = strategy.update(symbol, features)
        if not signal:
            continue

        direction = signal["direction"]
        entry_price = signal["entry_price"]

        # 3. Call Model Service (10-Model Ensemble) via HTTP
        prediction = await model_client.get_prediction(symbol, timestamp, features)
        if not prediction:
            continue

        # 4. Log raw strategy signal (always — for analytics)
        raw_signal = StrategySignal(
            symbol=symbol,
            timestamp=timestamp,
            strategy_name=strategy.name,
            direction=direction,
            entry_price=entry_price,
            probability=prediction["probability"],
            expected_return=prediction["expected_return"],
            expected_drawdown=prediction["expected_drawdown"],
            regime=regime,
            is_anomaly=prediction["is_anomaly"],
            backtest_id=backtest_id,
        )
        db.add(raw_signal)
        db.commit()

        # 5. Strict Signal Filter — gatekeeper, no exceptions
        if signal_filter.filter(prediction, allowed, strategy.name):
            # 6. Calculate institutional 3-level targets (L1/L2/L3)
            atr = features.get("atr_14") or 0.01
            targets = target_calculator.calculate(entry_price, direction, atr)

            # 7. Generate execution-ready trade alert
            trade_alert = TradeSignal(
                symbol=symbol,
                timestamp=timestamp,
                strategy_name=strategy.name,
                direction=direction,
                entry=targets["entry"],
                stop_loss=targets["stop_loss"],
                target_l1=targets["target_l1"],
                target_l2=targets["target_l2"],
                target_l3=targets["target_l3"],
                probability=prediction["probability"],
                confidence=prediction["confidence"],
                regime=regime,
                backtest_id=backtest_id,
            )
            db.add(trade_alert)
            db.commit()
            db.refresh(trade_alert)

            # AI Validation removed as per user request (Gemma is slow)
            ai_result = None


            if AUTO_PAPER_TRADING_ENABLED and not backtest_id:
                auto_side = "BUY" if direction.upper() == "BUY" else "SHORT"
                conviction = ai_result.get("conviction", "LOW") if ai_result else "LOW"
                
                order_payload = {
                    "symbol": symbol,
                    "side": auto_side,
                    "qty": AUTO_PAPER_TRADING_QTY,
                    "requested_price": targets["entry"],
                    "strategy_name": strategy.name,
                    "regime": regime,
                    "order_id": trade_alert.id,
                    "conviction": conviction,
                    "extra": {
                        "stop_loss": targets["stop_loss"],
                        "target_l1": targets["target_l1"],
                        "target_l2": targets["target_l2"],
                        "target_l3": targets["target_l3"],
                        "probability": prediction["probability"],
                        "ai_thesis": ai_result.get("thesis") if ai_result else "No AI Thesis Generated",
                    },
                }
                paper_order = await paper_client.create_order(order_payload)
                if paper_order:
                    trade_alert.status = f"AUTO_PAPER_{paper_order['status']}"
                else:
                    trade_alert.status = "AUTO_PAPER_SUBMIT_FAILED"
                db.commit()

            logging.info(
                f"🚀 TRADER ALERT: {symbol} | {strategy.name} | {direction} "
                f"| prob={prediction['probability']:.2f} | conf={prediction['confidence']:.2f}"
            )
            generated_alerts.append({"strategy": strategy.name, "direction": direction})

    if generated_alerts:
        return {"status": "signals_generated", "symbol": symbol, "alerts": generated_alerts}

    return {"status": "no_signal", "symbol": symbol, "regime": regime}


@app.get("/symbols", response_model=SymbolsListResponse)
def get_symbols(db: Session = Depends(get_db)):
    service = MarketDataService(db)
    symbols = service.get_symbols()
    return SymbolsListResponse(status="success", data=symbols)


@app.get("/history", response_model=HistoryResponse)
def get_history(symbol: str, range: str = "1D", limit: Optional[int] = 500, db: Session = Depends(get_db)):
    service = MarketDataService(db)
    history = service.get_history(symbol, range, limit=limit)
    return HistoryResponse(status="success", data={
        "symbol": symbol,
        "range": range,
        "series": history
    })


@app.get("/benchmark", response_model=BenchmarkResponse)
def get_benchmark(range: str = "1D", limit: Optional[int] = 60, db: Session = Depends(get_db)):
    service = MarketDataService(db)
    benchmark = service.get_benchmark(range, limit=limit)
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark data not found")
    return BenchmarkResponse(status="success", data=benchmark)


@app.get("/insights", response_model=InsightsResponse)
async def get_insights(symbol: str, db: Session = Depends(get_db)):
    """
    Aggregate strategy diagnostics and latest prediction for a symbol.
    """
    try:
        # 1. Latest price and stats
        latest_ohlcv = db.query(OHLCVEnriched).filter(OHLCVEnriched.symbol == symbol).order_by(OHLCVEnriched.timestamp.desc()).first()
        
        if not latest_ohlcv:
            raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")
            
        # 2. Convert to features dict for strategies (ensure no None values for numeric types)
        features = {}
        for c in latest_ohlcv.__table__.columns:
            val = getattr(latest_ohlcv, c.name)
            if val is None and isinstance(c.type, Float):
                features[c.name] = 0.0
            else:
                features[c.name] = val or 0.0 if isinstance(val, (int, float)) else val
        
        # Add transient features (e.g. minutes from open)
        ts = latest_ohlcv.timestamp
        market_open = ts.replace(hour=9, minute=15, second=0, microsecond=0)
        features["minutes_from_open"] = int((ts - market_open).total_seconds() / 60)
        features["high"] = latest_ohlcv.high
        features["low"] = latest_ohlcv.low
        features["close"] = latest_ohlcv.close
        features["volume_spike_ratio"] = features.get("volume_spike_ratio", 1.0) # Fallback

        # 3. Latest prediction if available (from strategy_signals)
        latest_strategy_signal = db.query(StrategySignal).filter(StrategySignal.symbol == symbol).order_by(StrategySignal.timestamp.desc()).first()
        
        # --- On-Demand Prediction Logic ---
        # If no signal in DB, or it's old, trigger a real-time prediction
        prediction_data = None
        if latest_strategy_signal:
            prediction_data = {
                "probability": latest_strategy_signal.probability,
                "expected_return": latest_strategy_signal.expected_return,
                "expected_drawdown": latest_strategy_signal.expected_drawdown,
                "confidence": 0.82,
                "source_status": "historical",
                "is_anomaly": latest_strategy_signal.is_anomaly
            }
        else:
            # Trigger real-time model prediction
            logging.info(f"🚀 Triggering ON-DEMAND prediction for {symbol}")
            pred = await model_client.get_prediction(symbol, str(ts), features)
            if pred:
                prediction_data = {
                    "probability": pred.get("probability", 0.5),
                    "expected_return": pred.get("expected_return", 0.0),
                    "expected_drawdown": pred.get("expected_drawdown", 0.0),
                    "confidence": 0.88,
                    "source_status": "live_on_demand",
                    "is_anomaly": pred.get("is_anomaly", False),
                    "models_used": pred.get("models_used", [])
                }

        # 4. Strategy statuses (The 7-Strategy Engine)
        strategy_diagnostics = []
        
        # Strategy 7: Regime (Special Case)
        regime_diag = regime_classifier.get_diagnostics(features)
        strategy_diagnostics.append({
            "name": "Market Regime",
            "status": regime_diag["status"],
            "confidence": 1.0,
            "note": regime_diag["note"],
            "last_signal_time": str(ts)
        })

        # Strategies 1-6
        for strategy in strategies:
            diag = strategy.get_diagnostics(symbol, features)
            
            # Check if there was a historical signal (to override status if bullish/bearish)
            last_s = db.query(StrategySignal).filter(
                StrategySignal.symbol == symbol, 
                StrategySignal.strategy_name == strategy.name
            ).order_by(StrategySignal.timestamp.desc()).first()
            
            status = diag["status"]
            note = diag["note"]
            
            if last_s:
                 # If we have a past signal, we can enrich the note
                 sig_time = last_s.timestamp.strftime('%H:%M')
                 note = f"{note} (Last Signal: {last_s.direction} at {sig_time})"
            
            strategy_diagnostics.append({
                "name": strategy.name,
                "status": status,
                "confidence": diag.get("confidence", 0.0),
                "note": note,
                "last_signal_time": str(last_s.timestamp) if last_s else "N/A"
            })

        return InsightsResponse(status="success", data={
            "symbol": symbol,
            "last_price": latest_ohlcv.close,
            "regime": latest_strategy_signal.regime if latest_strategy_signal else regime_diag["status"],
            "latest_model_prediction": prediction_data or {
                "probability": 0.5,
                "expected_return": 0.0,
                "expected_drawdown": 0.0,
                "confidence": 0.0,
                "source_status": "unavailable"
            },
            "strategies": strategy_diagnostics
        })
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in get_insights for {symbol}: {e}")
        return InsightsResponse(status="error", data={}, error=str(e))


@app.get("/signals", response_model=SignalsListResponse)
def get_active_signals(db: Session = Depends(get_db)):
    """
    Fetch all filtered trade alerts for the Frontend Dashboard.
    Ordered by most recent first.
    """
    signals = db.query(TradeSignal).order_by(TradeSignal.timestamp.desc()).limit(500).all()

    response_data = [
        SignalResponse(
            id=s.id,
            symbol=s.symbol,
            strategy=s.strategy_name,
            direction=s.direction,
            entry=s.entry,
            stop_loss=s.stop_loss,
            target_l1=s.target_l1,
            target_l2=s.target_l2,
            target_l3=s.target_l3,
            probability=s.probability,
            confidence=s.confidence,
            regime=s.regime,
            timestamp=str(s.timestamp),
            status=s.status,
        )
        for s in signals
    ]

    return SignalsListResponse(status="success", data=response_data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7004, log_level="info")
