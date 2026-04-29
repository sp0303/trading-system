import logging
import os
from typing import Any, Dict, Optional

import httpx


class PaperTradingClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("PAPER_TRADING_SERVICE_URL", "http://127.0.0.1:7012")

    async def create_order(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.base_url}/orders", json=payload, timeout=20.0)
                response.raise_for_status()
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")
                logging.error("Paper trading service returned error: %s", result)
            except Exception as exc:
                logging.error("Paper trading request failed: %s", exc)
        return None
