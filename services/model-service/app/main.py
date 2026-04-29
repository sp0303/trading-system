from fastapi import FastAPI
from app.schemas.prediction import FeatureInput, PredictionResponse, ModelPrediction
from app.services.ensemble import EnsemblePredictor
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Nifty 500 Model Service")

# --- Monitoring ---
MODEL_REQUEST_COUNT = Counter("model_service_requests_total", "Total requests", ["status"])
MODEL_REQUEST_LATENCY = Histogram("model_service_request_latency_seconds", "Request latency")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Initialize global predictor
predictor = None

@app.on_event("startup")
def startup_event():
    global predictor
    try:
        predictor = EnsemblePredictor()
    except Exception as e:
        print(f"CRITICAL: Failed to load EnsemblePredictor: {e}")

@app.get("/health")
def health_check():
    return {
        "status": "ok" if predictor else "loading",
        "service": "model-service"
    }

@app.post("/predict", response_model=PredictionResponse)
def predict(input_data: FeatureInput):
    """
    Generate ensemble predictions using all available agents and detect anomalies.
    """
    if not predictor:
        return PredictionResponse(status="error", data=None, error="Model service is still initializing or failed to load.")
        
    try:
        # Generate predictions using the ensemble
        preds = predictor.predict(input_data.features)
        
        MODEL_REQUEST_COUNT.labels(status="success").inc()
        
        # As per README, regime is determined by a separate logic (Strategy 7).
        # For the model service output, we provide 'Trending' as a default regime 
        # unless more complex regime logic is added.
        regime = "Trending" 

        return PredictionResponse(
            status="success",
            data=ModelPrediction(
                symbol=input_data.symbol,
                probability=preds["probability"],
                expected_return=preds["expected_return"],
                expected_drawdown=preds["expected_drawdown"],
                confidence=preds["confidence"],
                regime=regime,
                is_anomaly=preds["is_anomaly"],
                models_used=preds["models_used"]
            ),
            error=None
        )
    except Exception as e:
        return PredictionResponse(status="error", data=None, error=f"Prediction failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7003)
