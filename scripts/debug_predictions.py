import pandas as pd
import os
import sys
import logging

# Setup Paths
SIGNAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "signal-service"))
MODEL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "model-service"))

for path in [SIGNAL_ROOT, MODEL_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.ensemble import EnsemblePredictor
from app.services.signal_filter import SignalFilter
from app.strategies.orb import ORBStrategy

logging.basicConfig(level=logging.INFO, format='%(message)s')

def debug_sample(symbol="RELIANCE"):
    data_path = f"data/mode_ready_data/{symbol}_enriched.parquet"
    if not os.path.exists(data_path):
        print(f"File not found: {data_path}")
        return

    print(f"--- DEBUGGING PREDICTIONS FOR {symbol} ---")
    df = pd.read_parquet(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Take a sample of potential signals (where strategy might fire)
    strategy = ORBStrategy()
    predictor = EnsemblePredictor()
    # Default thresholds: 0.70 prob, 0.3 mfe, 1.0 mae
    filter_service = SignalFilter(prob_threshold=0.70, mfe_threshold=0.3, mae_threshold=1.0)
    
    signals_checked = 0
    passed_count = 0
    
    # We only need a few samples
    for i, row in df.iterrows():
        features = row.to_dict()
        signal = strategy.update(symbol, features)
        
        if signal:
            signals_checked += 1
            # Extract numeric features for model
            # Note: EnsemblePredictor handles the dict to DataFrame conversion
            numeric_cols = [c for c in df.columns if df[c].dtype in ['float32', 'float64', 'int64'] and c not in ['target', 'target_prob', 'target_mfe', 'target_mae', 'id']]
            numeric_features = {c: features.get(c, 0) for c in numeric_cols}
            
            prediction = predictor.predict(numeric_features)
            
            allowed_strategies = ["ORB", "Momentum", "VWAP", "Vol Squeeze", "Vol Reversal", "Relative Strength"]
            passed = filter_service.filter(prediction, allowed_strategies, strategy.name)
            
            print(f"\n[SIGNAL {signals_checked}] {signal['timestamp']} | {signal['direction']}")
            print(f"  Predicted Prob: {prediction['probability']:.4f} (Req: >0.70)")
            print(f"  Predicted MFE:  {prediction['expected_return']:.4f} (Req: >0.3)")
            print(f"  Predicted MAE:  {prediction['expected_drawdown']:.4f} (Req: <1.0)")
            print(f"  Filter Passed:  {'✅ YES' if passed else '❌ NO'}")
            
            if passed: passed_count += 1
            if signals_checked >= 20: break

    print(f"\nSummary: {signals_checked} signals checked, {passed_count} passed.")

if __name__ == "__main__":
    debug_sample("RELIANCE")
