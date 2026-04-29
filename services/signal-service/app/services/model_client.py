import httpx
import logging
from typing import Dict, Any, Optional

class ModelServiceClient:
    def __init__(self, base_url: str = "http://localhost:7003"):
        self.base_url = base_url
        logging.info(f"ModelServiceClient initialized with base_url: {self.base_url}")

    async def get_prediction(self, symbol: str, timestamp: str, features: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        Calls the Model Service (Port 7003) to get ensemble predictions.
        """
        async with httpx.AsyncClient() as client:
            try:
                # Institutional Handoff Protocol: Sparse Selection
                # 1. Remove metadata keys
                # 2. Transmit ONLY valid numeric features
                # 3. Omit None/NaN to allow Model Service internal defaults
                sanitized_features = {}
                for k, v in features.items():
                    if k in ["symbol", "timestamp"]:
                        continue
                    if v is not None:
                        try:
                            # Verify it's effectively a number
                            val = float(v)
                            sanitized_features[k] = val
                        except (ValueError, TypeError):
                            continue # Omit non-numeric/unsupported features
                
                payload = {
                    "symbol": symbol,
                    "timestamp": str(timestamp),
                    "features": sanitized_features
                }
                # Timeout is generous to allow for ensemble processing
                response = await client.post(f"{self.base_url}/predict", json=payload, timeout=20.0)
                response.raise_for_status()
                
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")
                else:
                    logging.error(f"Model service returned error for {symbol}: {result.get('error')}")
                    return None
            except httpx.HTTPStatusError as e:
                logging.error(f"HTTP error calling model service for {symbol}: {e}")
                return None
            except Exception as e:
                logging.error(f"Unexpected error calling model service for {symbol}: {e}")
                return None
