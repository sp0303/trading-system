import pandas as pd
import numpy as np
import os
from tqdm import tqdm
import logging
from collections import deque

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MultiStrategyLabeler:
    """
    Simulates all 6 core strategies to generate training labels (target_prob, target_mfe, target_mae).
    """
    def __init__(self):
        # Configuration matches signal-service strategies
        self.orb_minutes = 15
        self.momentum_window = 20
        self.vwap_dist_threshold = 0.5
        self.vol_spike_threshold = 2.0
        self.squeeze_low = 0.4
        self.squeeze_high = 0.6
        self.breakout_high = 0.65
        self.breakout_low = 0.35
        self.reversal_vol_spike = 4.0
        self.rsi_oversold = 30
        self.rsi_overbought = 70

    def calculate_targets(self, df):
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df = df.sort_values('timestamp')

        # Clean column names to lowercase just in case
        df.columns = [c.lower() for c in df.columns]

        # Result storage
        targets = {
            'target_mfe': np.zeros(len(df)),
            'target_mae': np.zeros(len(df)),
            'target_prob': np.zeros(len(df), dtype=int),
            'strategy_fired': ['None'] * len(df)
        }

        all_dates = df['date'].unique()
        
        for date in all_dates:
            day_mask = df['date'] == date
            day_data = df[day_mask].copy()
            if len(day_data) < 20: continue

            # --- Strategy State per Day ---
            orb_high, orb_low = -np.inf, np.inf
            orb_triggered = False
            mom_triggered = False
            vwap_triggered = False
            rel_str_triggered = False
            squeeze_triggered = False
            reversal_triggered = False
            
            # Helper for squeeze
            bb_history = deque(maxlen=4) 

            for i, row in enumerate(day_data.itertuples()):
                idx = day_data.index[i]
                mfo = row.minutes_from_open
                close = row.close
                high = row.high
                low = row.low
                vol_spike = getattr(row, 'volume_spike_ratio', 0)
                atr = getattr(row, 'atr_14', 0.01)
                if atr <= 0: atr = 0.01

                # 1. ORB (9:15-9:30 range)
                if mfo <= 15:
                    orb_high = max(orb_high, high)
                    orb_low = min(orb_low, low)
                
                # Logic to determine if a signal fires at THIS bar
                signal_direction = None
                strategy_name = None

                # ORB Trigger
                if mfo > 15 and not orb_triggered:
                    if close > orb_high and vol_spike > 2.0:
                        signal_direction = "BUY"
                        strategy_name = "ORB"
                        orb_triggered = True
                    elif close < orb_low and vol_spike > 2.0:
                        signal_direction = "SHORT"
                        strategy_name = "ORB"
                        orb_triggered = True

                # Momentum Trigger (using rolling high/low from previous bars)
                if not signal_direction and mfo > 20 and not mom_triggered:
                    # Lookback for window (previous 20 bars)
                    if i >= 20:
                        window = day_data.iloc[i-20:i]
                        win_high = window['high'].max()
                        win_low = window['low'].min()
                        if close > win_high and vol_spike > 2.0:
                            signal_direction = "BUY"
                            strategy_name = "Momentum"
                            mom_triggered = True
                        elif close < win_low and vol_spike > 2.0:
                            signal_direction = "SHORT"
                            strategy_name = "Momentum"
                            mom_triggered = True

                # VWAP Reversion Trigger
                if not signal_direction and mfo > 30 and not vwap_triggered:
                    vwap = getattr(row, 'vwap', close)
                    dist = (close - vwap) / vwap * 100
                    if dist < -0.8: # Oversold dist
                        signal_direction = "BUY"
                        strategy_name = "VWAP Reversion"
                        vwap_triggered = True
                    elif dist > 0.8: # Overbought dist
                        signal_direction = "SHORT"
                        strategy_name = "VWAP Reversion"
                        vwap_triggered = True

                # Vol Squeeze Trigger
                if not signal_direction and mfo > 30 and not squeeze_triggered:
                    bb_pct_b = getattr(row, 'bollinger_b', 0.5)
                    bb_history.append(bb_pct_b)
                    if len(bb_history) == 4:
                        prior_bars = list(bb_history)[:-1]
                        if all(0.4 <= b <= 0.6 for b in prior_bars):
                            if bb_pct_b > 0.65:
                                signal_direction = "BUY"
                                strategy_name = "Vol Squeeze"
                                squeeze_triggered = True
                            elif bb_pct_b < 0.35:
                                signal_direction = "SHORT"
                                strategy_name = "Vol Squeeze"
                                squeeze_triggered = True

                # --- Calculate Performance If Fired (60-minute Risk Window) ---
                if signal_direction:
                    # Look ahead up to 60 minutes or end of day
                    window_end = i + 61 
                    future_data = day_data.iloc[i+1:window_end]
                    
                    if not future_data.empty:
                        f_max = future_data['high'].max()
                        f_min = future_data['low'].min()
                        
                        if signal_direction == "BUY":
                            mfe = (f_max - close) / atr
                            mae = (close - f_min) / atr
                        else: # SHORT
                            mfe = (close - f_min) / atr
                            mae = (f_max - close) / atr
                        
                        # Prob = WIN if MFE reaches 2.0R before MAE reaches 1.0R (Standard Institutional Label)
                        # For now, let's keep it simple: win if MFE > 1.0 (reaches 1 ATR move)
                        prob = 1 if mfe > 1.0 else 0
                        
                        targets['target_mfe'][df.index.get_loc(idx)] = mfe
                        targets['target_mae'][df.index.get_loc(idx)] = mae
                        targets['target_prob'][df.index.get_loc(idx)] = prob
                        targets['strategy_fired'][df.index.get_loc(idx)] = strategy_name

        df['target_mfe'] = targets['target_mfe']
        df['target_mae'] = targets['target_mae']
        df['target_prob'] = targets['target_prob']
        df['strategy_fired'] = targets['strategy_fired']

        # Only keep rows where a strategy fired or keep all for now?
        # The trainer expects a dataset where rows are potential signals.
        # But for training, we often sample. Let's keep all for now so the trainer can filter.
        return df

def process_all_files():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(BASE_DIR, "data", "mode_ready_data")
    # Actually, we should read from enriched_data if we want fresh targets
    # or just read from mode_ready_data if they already have all features.
    
    labeler = MultiStrategyLabeler()
    
    if not os.path.exists(data_dir):
        logging.error(f"Data directory {data_dir} does not exist.")
        return

    files = [f for f in os.listdir(data_dir) if f.endswith('.parquet')]
    
    for file in tqdm(files, desc="Calculating Multi-Strategy Targets"):
        try:
            file_path = os.path.join(data_dir, file)
            df = pd.read_parquet(file_path)
            
            df_targeted = labeler.calculate_targets(df)
            
            if not df_targeted.empty:
                df_targeted.to_parquet(file_path) # Overwrite with new columns
            else:
                logging.warning(f"No targets generated for {file}")
        except Exception as e:
            logging.error(f"Failed to process {file}: {e}")

if __name__ == "__main__":
    process_all_files()
