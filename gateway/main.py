import logging
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import subprocess


# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Nifty 500 API Gateway")

# Enable CORS for Frontend (port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs — defaults to localhost for host-based deployment
# Override with env vars for Docker-based deployment
SERVICES = {
    "model": os.getenv("MODEL_SERVICE_URL", "http://localhost:7003"),
    "signal": os.getenv("SIGNAL_SERVICE_URL", "http://localhost:7004"),
    "news": os.getenv("NEWS_SERVICE_URL", "http://localhost:7007"),
    "fundamentals": os.getenv("FUNDAMENTALS_SERVICE_URL", "http://localhost:7008"),
    "institutional": os.getenv("INSTITUTIONAL_SERVICE_URL", "http://localhost:7009"),
    "sentiment": os.getenv("SENTIMENT_SERVICE_URL", "http://localhost:7007"),
    "ai": os.getenv("AI_SERVICE_URL", "http://localhost:7011"),
    "paper": os.getenv("PAPER_SERVICE_URL", "http://localhost:7012"),
}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "gateway"}

async def proxy_request(service_key: str, path: str, request: Request):
    base_url = SERVICES.get(service_key)
    if not base_url:
        raise HTTPException(status_code=500, detail="Service configuration error")
    
    url = f"{base_url}/{path}"
    
    # Extract query params
    params = dict(request.query_params)
    
    async with httpx.AsyncClient() as client:
        try:
            if request.method == "GET":
                response = await client.get(url, params=params, timeout=120.0)
            elif request.method == "POST":
                try:
                    body = await request.json()
                except:
                    body = None
                response = await client.post(url, json=body, timeout=120.0)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            try:
                content = response.json()
            except json.JSONDecodeError:
                content = {"status": "error", "error": response.text or "Upstream service returned a non-JSON response"}

            return JSONResponse(status_code=response.status_code, content=content)
        except Exception as e:
            logging.error(f"Error proxying to {url}: {e}")
            raise HTTPException(status_code=502, detail=f"Service {service_key} unavailable: {str(e)}")

# Signal Service Routes
@app.get("/signals")
async def get_signals(request: Request):
    return await proxy_request("signal", "signals", request)

@app.get("/symbols")
async def get_symbols(request: Request):
    return await proxy_request("signal", "symbols", request)

@app.get("/history")
async def get_history(request: Request):
    return await proxy_request("signal", "history", request)

@app.get("/benchmark")
async def get_benchmark(request: Request):
    return await proxy_request("signal", "benchmark", request)

@app.get("/insights")
async def get_insights(request: Request):
    return await proxy_request("signal", "insights", request)

# Model Service Routes
@app.post("/predict")
async def predict(request: Request):
    return await proxy_request("model", "predict", request)

@app.post("/model/predict")
async def model_predict(request: Request):
    return await proxy_request("model", "predict", request)


# News Service Routes
@app.get("/news")
async def get_news(request: Request):
    return await proxy_request("news", "news", request)

# Fundamental Service Routes
@app.get("/fundamentals")
async def get_fundamentals(request: Request):
    return await proxy_request("fundamentals", "fundamentals", request)

@app.get("/analysis")
async def get_analysis(request: Request):
    return await proxy_request("fundamentals", "analysis", request)

# Institutional Service Routes
@app.get("/institutional-flow")
async def get_institutional_flow(request: Request):
    return await proxy_request("institutional", "institutional-flow", request)

# Sentiment Service Routes
@app.get("/sentiment")
async def get_sentiment(request: Request):
    return await proxy_request("sentiment", "sentiment", request)

@app.post("/ai-analyze")
async def ai_analyze(request: Request):
    return await proxy_request("ai", "analyze", request)

# Paper Trading Routes
@app.post("/paper/orders")
async def create_paper_order(request: Request):
    return await proxy_request("paper", "orders", request)

@app.get("/paper/orders")
async def get_paper_orders(request: Request):
    return await proxy_request("paper", "orders", request)

@app.get("/paper/fills")
async def get_paper_fills(request: Request):
    return await proxy_request("paper", "fills", request)

@app.get("/paper/positions")
async def get_paper_positions(request: Request):
    return await proxy_request("paper", "positions", request)

@app.post("/paper/positions/{symbol}/close")
async def close_paper_position(symbol: str, request: Request):
    return await proxy_request("paper", f"positions/{symbol}/close", request)

@app.get("/paper/account")
async def get_paper_account(request: Request):
    return await proxy_request("paper", "account", request)

@app.get("/paper/daily-pnl")
async def get_paper_daily_pnl(request: Request):
    return await proxy_request("paper", "daily-pnl", request)

@app.get("/paper/reports/daily")
async def get_paper_reports_daily(request: Request):
    return await proxy_request("paper", "reports/daily", request)

@app.post("/paper/orders/{symbol}/close")
async def close_paper_position_symbol(symbol: str, request: Request):
    return await proxy_request("paper", f"orders/{symbol}/close", request)

@app.post("/sync")
async def sync_data(force: bool = False, symbol: str = None):
    try:
        # Run sync_data.py as a separate process using the same python interpreter
        import sys
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "sync_data.py")
        
        cmd = [sys.executable, script_path]
        if force:
            cmd.append("--force")
        if symbol:
            cmd.extend(["--symbol", symbol])
            
        logging.info(f"Starting sync process: {' '.join(cmd)}")
        subprocess.Popen(cmd)
        
        target = f" for {symbol}" if symbol else " for all symbols"
        return {"status": "success", "message": f"Market data synchronization started{target} in background (Force={force})"}
    except Exception as e:
        logging.error(f"Failed to start sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Frontend Serving ---

frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve static assets if they exist
        file_path = os.path.join(frontend_dist, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {"message": "Gateway Running. Frontend not built. Run 'npm run build' in frontend folder."}

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 for Docker compatibility
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("GATEWAY_PORT", 8000))
    uvicorn.run(app, host=host, port=port)
