import os
import logging
import httpx
from fastapi import FastAPI, HTTPException, Query
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from textblob import TextBlob
from typing import Optional

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Nifty 50 Sentiment Service")

# Use env var so this works both on host and in Docker
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "ok", "service": "sentiment-service"}

@app.get("/sentiment")
async def get_sentiment(symbol: str = Query(...)):
    try:
        # 1. Fetch recent news headlines for this symbol from the News Service via Gateway
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GATEWAY_URL}/news", params={"symbol": symbol})
            news_data = resp.json()

        headlines = [item['title'] for item in news_data.get('data', [])]

        if not headlines:
            # Fallback to general market news
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{GATEWAY_URL}/news")
                news_data = resp.json()
            headlines = [item['title'] for item in news_data.get('data', [])]

        # 2. Analyze sentiment
        scores = []
        for text in headlines:
            analysis = TextBlob(text)
            scores.append(analysis.sentiment.polarity)

        avg_sentiment = sum(scores) / len(scores) if scores else 0

        # 3. Label sentiment
        label = "Neutral"
        if avg_sentiment > 0.15:
            label = "Bullish"
        elif avg_sentiment > 0.05:
            label = "Slightly Bullish"
        elif avg_sentiment < -0.15:
            label = "Bearish"
        elif avg_sentiment < -0.05:
            label = "Slightly Bearish"

        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "score": round(avg_sentiment, 3),
                "label": label,
                "headline_count": len(headlines)
            }
        }
    except Exception as e:
        logging.error(f"Error calculating sentiment for {symbol}: {e}")
        # Return neutral on error instead of crashing
        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "score": 0.0,
                "label": "Neutral",
                "headline_count": 0,
                "note": "News service unavailable"
            }
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7010)
