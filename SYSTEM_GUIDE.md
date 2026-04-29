# Nifty 500 Trading System: Comprehensive Guide

This guide provides a complete overview of the system architecture, data pipeline, model training process, and how to run the full stack.

---

## 🏗️ System Architecture

The project is built on a high-concurrency microservices architecture:

1.  **API Gateway (Port 8000)**: The single entry point that orchestrates requests between the Frontend and Backend services.
2.  **Signal Service (Port 7004)**: The core engine that runs 7 quantitative strategies (ORB, Momentum, VWAP Reversion, Relative Strength, Volatility Squeeze, Volume Reversal, and Regime Classifier).
3.  **Model Service (Port 7003)**: An ML-inference service that uses a 10-model ensemble (XGBoost, CatBoost, Random Forest, etc.) to predict the probability and risk (MAE/MFE) for every signal.
5.  **News Service (Port 7007)**: Ingests real-time market news via RSS feeds.
6.  **Fundamental Service (Port 7008)**: Fetches key financial metrics using yfinance.
7.  **Institutional Service (Port 7009)**: Tracks symbol-specific delivery and FII activity using nsepython.
8.  **Sentiment Service (Port 7010)**: Scores market sentiment based on headlines using TextBlob.
9.  **AI Service (Port 7011)**: Orchestrates Gemma 2B (via Ollama) to provide institutional reasoning for signals.
10. **Frontend (Port 3000)**: A **TypeScript-based React** dashboard with a Unified Stock Analysis page.

---

## ⚙️ Setup & Configuration

### 1. Environment Variables
Create a `.env` file in the root directory with the following:

```env
DATABASE_URL=postgresql://trading:Trading%40123@localhost:5432/tradingsystem
ANGEL_CLIENT_ID=your_id
ANGEL_PIN=your_pin
ANGEL_API_KEY=your_key
ANGEL_TOTP_SECRET=your_totp_secret
```

### 2. Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
pip install smartapi-python pyotp pandas-ta PyWavelets statsmodels logzero websocket-client pytz feedparser nsepython yfinance textblob ollama --break-system-packages
```

### 3. AI Prerequisites
Ensure **Ollama** is running locally and the Gemma model is available:
```bash
ollama pull gemma:2b
```

---

## 🔄 Data Pipeline (History to Sync)

Before running the system, you must ensure your database is populated with enriched technical features.

### 1. Syncing from Angel One
To fetch missing data and calculate technical indicators (RSI, MACD, etc.):
```bash
python scripts/sync_data.py
```
This script queries the latest `timestamp` in your DB and fetches missing 1-minute candles from Angel One for the ~80 Nifty stocks.

### 2. Exporting for Training
The ML models are trained on Local Parquet files for maximum speed. Export your DB data to Parquet:
```bash
python scripts/training/export_db_to_parquet.py
```
This saves symbol-specific `.parquet` files into `data/mode_ready_data/`.

---

## 🧠 Model Training

The system uses a 10-model stacked ensemble for high-conviction filtering.

### 1. Running the Trainer
```bash
python scripts/training/train_ensemble.py --start-date 2023-01-01 --end-date 2024-12-31 --max-rows 1200000
```
- **Inputs**: Parquet files in `data/mode_ready_data/`.
- **Outputs**: Trained `.joblib` models in `services/model-service/app/models/`.
- **Logic**: Trains individual models (XGB, RF, CatBoost, etc.) and a **Meta-model** (Logistic Regression for probability, Huber for return).

---

## 🚀 Running the Full Stack

Open 4 terminal windows and run the following in order:

### 1. Model Service (Port 7003)
```bash
cd services/model-service
export PYTHONPATH=$PYTHONPATH:.
python app/main.py
```

### 2. Signal Service (Port 7004)
```bash
cd services/signal-service
export PYTHONPATH=$PYTHONPATH:.
python app/main.py
```

### 3. API Gateway (Port 8000)
```bash
python gateway/main.py
```

### 4. Institutional & AI Services
Open additional terminals and run:
```bash
python services/news-service/app/main.py
python services/fundamental-service/app/main.py
python services/institutional-service/app/main.py
python services/sentiment-service/app/main.py
python services/ai-service/app/main.py
```
*(Tip: In development, you can run them in the background with `&`)*

### 5. Frontend (Port 3000)
```bash
cd frontend
npm run dev
```

---

## 📈 Backtesting & Auditing

To verify your performance without running the live services:
```bash
python services/signal-service/scripts/mass_backtest.py
```
This script bypasses the HTTP gateway and runs a direct simulation on your local data, outputting a PnL audit.

---

## 🛠️ Internal Feature Engineering
Every synced row in `ohlcv_enriched` contains **71 features**. Key groups include:
- **Momentum**: `rsi_14`, `macd_hist`, `adx_14`
- **Volatility**: `atr_14`, `bollinger_b`, `volatility_20d`
- **Advanced**: `frac_diff_close` (Fractional Differentiation), `wavelet_return` (Denoised price action)
- **Context**: `nifty_return`, `relative_strength` (Performance vs Index)
