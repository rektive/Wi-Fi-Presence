"""FastAPI core application, static file serving, and WebSocket telemetry pipeline."""

import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from config.settings import settings
from src.server.websocket_manager import WebSocketManager

app = FastAPI(title="Wi-Fi Presence & Headcount Detector")
ws_manager = WebSocketManager()

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def get_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/status")
async def get_status():
    baseline_loaded = settings.BASELINE_STATE_PATH.exists()
    model_loaded = settings.HEADCOUNT_MODEL_PATH.exists()
    baseline_data = {}

    if baseline_loaded:
        try:
            with open(settings.BASELINE_STATE_PATH, "r", encoding="utf-8") as f:
                baseline_data = json.load(f)
        except Exception:
            pass

    return {
        "interface": settings.WIFI_INTERFACE,
        "capture_mode": settings.CAPTURE_MODE,
        "sampling_rate_hz": settings.SAMPLING_RATE_HZ,
        "baseline_calibrated": baseline_loaded,
        "headcount_model_loaded": model_loaded,
        "baseline_info": baseline_data,
    }


@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep socket alive and listen for client heartbeats
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
