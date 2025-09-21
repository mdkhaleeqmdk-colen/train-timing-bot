from __future__ import annotations
import os
import requests
from typing import Dict, Any, Optional

BASE = "https://transportapi.com/v3/uk/train/station/"
APP_ID = os.getenv("TRANSPORTAPI_APP_ID")
APP_KEY = os.getenv("TRANSPORTAPI_APP_KEY")

class TransportAPI:
    @staticmethod
    def live_departures(
        crs: str,
        destination: Optional[str] = None,
        when: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        params = {
            "app_id": APP_ID,
            "app_key": APP_KEY,
            "darwin": "true",
            "live": "true",
            "limit": limit,
        }
        if when and when != "now":
            params["train_status"] = "passenger"
            params["type"] = "departure"
            params["dt"] = when

        url = f"{BASE}{crs}/live.json"
        if destination:
            params["calling_at"] = destination

        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
