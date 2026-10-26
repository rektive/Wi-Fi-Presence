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



# ==========================================================
# Advanced Multi-Phase RF Calibration & Presets Engine
# ==========================================================
from src.analysis import presets
import collections
import time
import asyncio
import numpy as np
from pydantic import BaseModel

# High-resolution telemetry sample buffer: stores (timestamp, rssi, kinetic_energy)
calibration_sample_buffer = collections.deque(maxlen=2000)

class AdvancedPresetSaveReq(BaseModel):
    name: str
    vacant_stats: dict
    desk_stats: dict
    far_stats: dict
    d_desk: float = 0.9
    d_far: float = 2.4

@app.get("/api/presets")
async def get_presets_endpoint():
    data = presets.load_presets()
    return {
        "active": data.get("active", "Default"),
        "presets": list(data.get("presets", {}).values()),
        "count": len(data.get("presets", {})),
        "max": 3
    }

@app.post("/api/presets/activate")
async def activate_preset_endpoint(req: dict):
    name = req.get("name")
    prof = presets.set_active_preset(name)
    if not prof:
        return {"status": "error", "message": "Preset not found"}
    if hasattr(app.state, "proximity_tracker") and app.state.proximity_tracker:
        app.state.proximity_tracker.update_profile(
            desk_mean=prof["desk_mean"],
            away_mean=prof["away_mean"],
            ref_rssi=prof.get("ref_rssi_1m"),
            path_loss_n=prof.get("path_loss_n"),
            vacant_variance=prof.get("vacant_variance")
        )
    return {"status": "ok", "active": name, "profile": prof}

@app.post("/api/presets/sample")
async def sample_advanced_rf_phase():
    """High-resolution 5-second sampling of multi-path scatter and Doppler energy."""
    start_t = time.time()
    await asyncio.sleep(5.0)
    end_t = time.time()

    window_samples = [item for item in calibration_sample_buffer if item[0] >= start_t]
    duration = max(0.1, end_t - start_t)

    if len(window_samples) < 15:
        # Fallback to current tracker values if sniffer buffer is initializing
        fallback_rssi = -48.0
        if hasattr(app.state, "proximity_tracker") and app.state.proximity_tracker:
            fallback_rssi = getattr(app.state.proximity_tracker, "last_raw_rssi", -48.0)
        return {
            "mean_rssi": round(fallback_rssi, 2),
            "variance": 0.045,
            "kinetic_energy": 0.015,
            "sample_count": len(window_samples),
            "sample_rate": round(len(window_samples) / duration, 1),
            "fidelity": "LOW (Check illumi-ping)"
        }

    rssi_series = np.array([item[1] for item in window_samples], dtype=np.float32)
    kinetic_series = np.array([item[2] for item in window_samples], dtype=np.float32)

    mean_rssi = float(np.mean(rssi_series))
    var_rssi = float(np.var(rssi_series))
    mean_kinetic = float(np.mean(kinetic_series))
    rate_hz = round(len(window_samples) / duration, 1)

    return {
        "mean_rssi": round(mean_rssi, 2),
        "variance": round(var_rssi, 6),
        "kinetic_energy": round(mean_kinetic, 4),
        "sample_count": len(window_samples),
        "sample_rate": rate_hz,
        "fidelity": "OPTIMAL" if rate_hz >= 40 else "ACCEPTABLE"
    }

@app.post("/api/presets/save_advanced")
async def save_advanced_preset_endpoint(req: AdvancedPresetSaveReq):
    rf_matrix = presets.compute_rf_matrix(
        vacant_stats=req.vacant_stats,
        desk_stats=req.desk_stats,
        far_stats=req.far_stats,
        d_desk=req.d_desk,
        d_far=req.d_far
    )
    success = presets.add_advanced_preset(req.name, rf_matrix)
    if not success:
        return {"status": "error", "message": "Preset limit reached (Maximum 3)"}

    if hasattr(app.state, "proximity_tracker") and app.state.proximity_tracker:
        app.state.proximity_tracker.update_profile(
            desk_mean=rf_matrix["desk_mean"],
            away_mean=rf_matrix["away_mean"],
            ref_rssi=rf_matrix["ref_rssi_1m"],
            path_loss_n=rf_matrix["path_loss_n"],
            vacant_variance=rf_matrix["vacant_variance"]
        )
    return {"status": "ok", "name": req.name, "matrix": rf_matrix}

@app.post("/api/presets/delete")
async def delete_preset_endpoint(req: dict):
    name = req.get("name")
    if name == "Default":
        return {"status": "error", "message": "Cannot delete Default preset"}
    success = presets.delete_preset(name)
    if success and hasattr(app.state, "proximity_tracker") and app.state.proximity_tracker:
        active = presets.get_active_profile()
        app.state.proximity_tracker.update_profile(
            desk_mean=active["desk_mean"],
            away_mean=active["away_mean"],
            ref_rssi=active.get("ref_rssi_1m"),
            path_loss_n=active.get("path_loss_n")
        )
    return {"status": "ok" if success else "error"}
