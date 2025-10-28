# ============================================================
# queen/technicals/signals/tactical/mission_control_api.py
# ------------------------------------------------------------
# 🌐 Phase 7.4 — Mission Control API Hub
# Provides REST + WebSocket layer for external integrations:
# trading bots, alert systems, dashboards, and telemetry feeds.
# ============================================================

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rich.console import Console

console = Console()

# ============================================================
# 🧩 Config (to be centralized later in config.py)
# ============================================================
HEALTH_LOG = "quant/logs/supervisor_health.json"
WEIGHT_LOG = "quant/config/indicator_weights.json"
DRIFT_LOG = "quant/logs/meta_drift_log.csv"
EVENT_LOG = "quant/logs/tactical_event_log.csv"

app = FastAPI(title="🛰️ Quant Cockpit API Hub", version="1.0")

# Allow external dashboards or bots to connect easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 🧩 Utility Functions
# ============================================================
def read_json(path: str) -> Dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def read_csv(path: str, limit: int = 200) -> List[Dict]:
    if not os.path.exists(path):
        return []
    import csv

    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return rows[-limit:]


# ============================================================
# 📡 REST Endpoints
# ============================================================
@app.get("/status", response_class=JSONResponse)
def get_status():
    """Return high-level health summary."""
    health = read_json(HEALTH_LOG)
    weights = read_json(WEIGHT_LOG)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "health": health,
        "weights": weights,
        "status": "ok" if health else "unknown",
    }


@app.get("/events", response_class=JSONResponse)
def get_events(limit: int = 100):
    """Return latest tactical event logs."""
    return read_csv(EVENT_LOG, limit=limit)


@app.get("/drift", response_class=JSONResponse)
def get_drift(limit: int = 100):
    """Return latest model drift records."""
    return read_csv(DRIFT_LOG, limit=limit)


@app.post("/alert")
async def send_alert(request: Dict):
    """Simple inbound alert relay (to integrate external bots)."""
    payload = await request.json()
    console.print(f"📣 External alert received: {payload}")
    return {"status": "received", "payload": payload}


# ============================================================
# 🔌 WebSocket Stream
# ============================================================
connected_clients: List[WebSocket] = []


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    console.print(f"🔌 Client connected ({len(connected_clients)} active)")
    try:
        while True:
            # Stream live telemetry every few seconds
            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "health": read_json(HEALTH_LOG),
                "weights": read_json(WEIGHT_LOG),
            }
            await websocket.send_json(data)
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        console.print(f"⚡ Client disconnected ({len(connected_clients)} active)")


# ============================================================
# 🧪 Stand-alone Run
# ============================================================
if __name__ == "__main__":
    import uvicorn

    console.rule("[bold magenta]🛰️ Mission Control API Hub — Starting")
    console.print("🚀 REST endpoints live at http://127.0.0.1:9000")
    console.print("🔌 WebSocket live at ws://127.0.0.1:9000/ws/stream")
    uvicorn.run(app, host="0.0.0.0", port=9000)
