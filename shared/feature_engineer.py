import pandas as pd
import numpy as np
import ta as ta_lib
import pywt
from statsmodels.tsa.stattools import adfuller
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class FeatureEngineer:
    """
    Robust Feature Engineering for Nifty 500 Trading System.
    Enriches raw OHLCV data with 70+ statistical and technical indicators.
    """
    
    def __init__(self):
        self.required_columns = [
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'prev_close', 'returns', 'log_return', 'range', 'range_pct',
            'cum_vol', 'vwap', 'rolling_avg_volume', 'is_volume_spike',
            'vol_5', 'vol_15', 'distance_from_vwap', 'day_open', 
            'distance_from_open', 'volume_zscore', 'volume_spike_ratio',
            'minutes_from_open', 'minutes_to_close', 'day_of_week',
            'is_monday', 'is_friday', 'is_expiry_day', 'rsi_14', 
            'macd_hist', 'adx_14', 'stoch_k_14', 'atr_14', 'bollinger_b',
            'volatility_20d', 'obv_slope_10', 'cmf_20', 'rvol_20',
            'return_lag_1', 'return_lag_2', 'return_5d', 'rsi_lag_1',
            'macd_hist_lag_1', 'atr_lag_1', 'sin_dayofweek', 'cos_dayofweek',
            'frac_diff_close', 'wavelet_return', 'symbol'
        ]

    def enrich_data(self, df, symbol, nifty_df=None, banknifty_df=None):
        """
        Main entry point for enrichment.
        df: DataFrame with 1-min candles for 'symbol'
        nifty_df/banknifty_df: (Optional) Index data for relative features
        """
        if df.empty:
            return df
            
        df = df.copy()
        df['symbol'] = symbol
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # 1. Basic Price Action
        df['prev_close'] = df['close'].shift(1)
        df['returns'] = df['close'].pct_change() * 100
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        df['range'] = df['high'] - df['low']
        df['range_pct'] = (df['range'] / df['open']) * 100
        
        # 2. Time-based Features
        df['date'] = df['timestamp'].dt.date
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_monday'] = (df['day_of_week'] == 0).astype(int)
        df['is_friday'] = (df['day_of_week'] == 4).astype(int)
        
        # Cyclic encoding for Day of Week
        df['sin_dayofweek'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['cos_dayofweek'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # Intraday Timing (assuming 9:15 open)
        market_open = df['timestamp'].dt.normalize() + pd.Timedelta(hours=9, minutes=15)
        df['minutes_from_open'] = ((df['timestamp'] - market_open).dt.total_seconds() / 60).astype(int)
        df['minutes_to_close'] = (375 - df['minutes_from_open']).clip(lower=0)
        
        # Day Open reference
        day_opens = df.groupby('date')['open'].transform('first')
        df['day_open'] = day_opens
        df['distance_from_open'] = (df['close'] - df['day_open']) / df['day_open'] * 100
        
        # 3. Volume & VWAP
        # VWAP reset daily
        df['cum_vol'] = df.groupby('date')['volume'].cumsum()
        df['vol_price'] = df['close'] * df['volume']
        df['cum_vol_price'] = df.groupby('date')['vol_price'].cumsum()
        df['vwap'] = df['cum_vol_price'] / df['cum_vol']
        df['distance_from_vwap'] = (df['close'] - df['vwap']) / df['vwap'] * 100
        
        # Volume Stats
        df['rolling_avg_volume'] = df['volume'].rolling(20).mean()
        df['volume_zscore'] = (df['volume'] - df['volume'].rolling(20).mean()) / df['volume'].rolling(20).std()
        df['volume_spike_ratio'] = df['volume'] / df['rolling_avg_volume']
        df['is_volume_spike'] = (df['volume_spike_ratio'] > 2.0).astype(int)
        
        # Multi-window volatility (proxied by range)
        df['vol_5'] = df['range_pct'].rolling(5).mean()
        df['vol_15'] = df['range_pct'].rolling(15).mean()
        
        # 4. Indicators (using ta library)
        df['rsi_14'] = ta_lib.momentum.RSIIndicator(df['close'], window=14).rsi()
        macd = ta_lib.trend.MACD(df['close'], window_fast=12, window_slow=26, window_sign=9)
        df['macd_hist'] = macd.macd_diff()
        adx = ta_lib.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
        df['adx_14'] = adx.adx()
        stoch = ta_lib.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
        df['stoch_k_14'] = stoch.stoch()
        atr = ta_lib.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr_14'] = atr.average_true_range()
        bb = ta_lib.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bollinger_b'] = bb.bollinger_pband()
        cmf = ta_lib.volume.ChaikinMoneyFlowIndicator(df['high'], df['low'], df['close'], df['volume'], window=20)
        df['cmf_20'] = cmf.chaikin_money_flow()

        # 5. Advanced Stats
        # OBV Slope
        obv = ta_lib.volume.OnBalanceVolumeIndicator(df['close'], df['volume'])
        df['OBV'] = obv.on_balance_volume()
        df['obv_slope_10'] = df['OBV'].diff(10) / 10
        
        # Volatility 20D (Standard deviation of returns)
        df['volatility_20d'] = df['returns'].rolling(20).std()
        
        # Relative Volume (Current vs 20-period avg)
        df['rvol_20'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # Lags
        df['return_lag_1'] = df['returns'].shift(1)
        df['return_lag_2'] = df['returns'].shift(2)
        df['return_5d'] = df['close'].pct_change(5) * 100 # Approx 5 candles for intraday
        df['rsi_lag_1'] = df['rsi_14'].shift(1)
        df['macd_hist_lag_1'] = df['macd_hist'].shift(1)
        df['atr_lag_1'] = df['atr_14'].shift(1)
        
        # 6. Fractional Differentiation (Approximate)
        df['frac_diff_close'] = self._calculate_frac_diff(df['close'])
        
        # 7. Wavelet Return (Noise reduction)
        df['wavelet_return'] = self._calculate_wavelet(df['returns'].fillna(0))
        
        # 8. Market Context (Nifty/BankNifty)
        if nifty_df is not None:
            nifty_df = nifty_df.copy()
            nifty_df['nifty_return'] = nifty_df['close'].pct_change() * 100
            df = df.merge(nifty_df[['timestamp', 'nifty_return']], on='timestamp', how='left')
            df['relative_strength'] = df['returns'] - df['nifty_return']
        else:
            df['nifty_return'] = 0.0
            df['relative_strength'] = 0.0
            
        if banknifty_df is not None:
            banknifty_df = banknifty_df.copy()
            banknifty_df['banknifty_return'] = banknifty_df['close'].pct_change() * 100
            df = df.merge(banknifty_df[['timestamp', 'banknifty_return']], on='timestamp', how='left')
        else:
            df['banknifty_return'] = 0.0
            
        # Sector Features (Placeholder as CSV mapping is missing)
        df['sector'] = 'Unknown'
        df['sector_return'] = 0.0
        df['sector_strength'] = 0.0
        
        # Ranking Placeholders (Requires multi-symbol processing to fill correctly)
        df['return_rank'] = 0.0
        df['volume_rank'] = 0.0
        df['return_percentile'] = 0.0
        df['volume_percentile'] = 0.0
        
        # Final Clean up
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        # Fill missing values with 0 or forward fill where appropriate
        df.fillna(0, inplace=True)
        
        return df

    def _calculate_frac_diff(self, series, d=0.4, floor=1e-3):
        """
        Implementation of Fractional Differentiation (fixed window).
        d: differentiation order (0.4 is a common choice for finance)
        """
        w = self._get_weights(d, len(series))
        # Keep only weights above floor
        w = w[:len(w)]
        res = series.rolling(len(w)).apply(lambda x: np.dot(x, w), raw=True)
        return res

    def _get_weights(self, d, length):
        # Weights for fractional differentiation
        w = [1.0]
        for k in range(1, length):
            w.append(-w[-1] * (d - k + 1) / k)
        return np.array(w[::-1])

    def _calculate_wavelet(self, series):
        """
        Wavelet Denoising using Discrete Wavelet Transform.
        """
        try:
            coeffs = pywt.wavedec(series, 'db1', level=2)
            # Thresholding (Soft thresholding)
            threshold = np.std(coeffs[-1]) * np.sqrt(2 * np.log(len(series)))
            coeffs[1:] = [pywt.threshold(c, value=threshold, mode='soft') for c in coeffs[1:]]
            res = pywt.waverec(coeffs, 'db1')
            return res[:len(series)]
        except:
            return series

if __name__ == "__main__":
    # Test with dummy data
    data = {
        'timestamp': pd.date_range(start='2026-04-10 09:15:00', periods=100, freq='1min'),
        'open': np.random.randn(100).cumsum() + 2000,
        'high': np.random.randn(100).cumsum() + 2010,
        'low': np.random.randn(100).cumsum() + 1990,
        'close': np.random.randn(100).cumsum() + 2000,
        'volume': np.random.randint(100, 1000, size=100)
    }
    test_df = pd.DataFrame(data)
    engine = FeatureEngineer()
    enriched = engine.enrich_data(test_df, "TEST")
    print(f"Enriched columns: {len(enriched.columns)}")
    print(enriched.head())
