#!/usr/bin/env python3
"""Main execution entry point: orchestrates capture, DSP pipeline, and ASGI server."""

import asyncio
import collections
import json
import logging
import threading
import time
import numpy as np
import uvicorn
from config.settings import settings
from src.capture import MonitorSniffer, ActiveProber
from src.processing.filters import hampel_filter, butterworth_bandpass
from src.processing.baseline import DynamicBaseline
from src.analysis.features import extract_feature_vector
from src.detector.state_machine import RoomStateMachine, RoomState
from src.detector.crowd_estimator import CrowdEstimator
from src.server.app import app, ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WiFiPresenceMain")


def dsp_pipeline_loop(loop: asyncio.AbstractEventLoop):
    """Real-time signal processing thread."""
    logger.info("Initializing signal ingestion engine...")

    if settings.CAPTURE_MODE == "monitor":
        ingestor = MonitorSniffer(settings.WIFI_INTERFACE, settings.ROUTER_BSSID)
    else:
        ingestor = ActiveProber(settings.ROUTER_IP, rate_hz=settings.SAMPLING_RATE_HZ)

    ingestor.start()

    # Load baseline profile
    baseline_var = 0.05
    if settings.BASELINE_STATE_PATH.exists():
        try:
            with open(settings.BASELINE_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                baseline_var = data["baseline_metrics"]["variance"]
                logger.info(f"Loaded empty room baseline variance: {baseline_var:.6f}")
        except Exception as e:
            logger.warning(f"Could not load baseline JSON: {e}")

    state_machine = RoomStateMachine(
        base_threshold=baseline_var,
        sensitivity_multiplier=settings.SENSITIVITY_FACTOR,
    )
    crowd_estimator = CrowdEstimator(settings.HEADCOUNT_MODEL_PATH)
    baseline_tracker = DynamicBaseline(initial_variance=baseline_var)

    buffer = collections.deque(maxlen=settings.WINDOW_SIZE_SAMPLES)
    last_broadcast = 0.0
    broadcast_interval = 0.05  # 20 FPS UI updates

    logger.info("Signal processing engine active.")

    while True:
        sample = ingestor.get_sample(timeout=0.1)
        if sample is None:
            continue

        _, val = sample
        buffer.append(val)

        if len(buffer) >= (settings.WINDOW_SIZE_SAMPLES // 2):
            raw_win = np.array(buffer, dtype=np.float32)

            # Apply Hampel outlier rejection
            hampel_win = hampel_filter(
                raw_win,
                window_size=settings.HAMPEL_WINDOW,
                n_sigmas=settings.HAMPEL_N_SIGMA,
            )

            # Apply kinetic Doppler bandpass
            filtered_win = butterworth_bandpass(
                hampel_win,
                lowcut=settings.BANDPASS_LOW_HZ,
                highcut=settings.BANDPASS_HIGH_HZ,
                fs=settings.SAMPLING_RATE_HZ,
                order=settings.BUTTERWORTH_ORDER,
            )

            features = extract_feature_vector(hampel_win, filtered_win, fs=settings.SAMPLING_RATE_HZ)

            # Evaluate room state
            current_state, state_changed = state_machine.evaluate(
                current_variance=features.variance,
                kinetic_energy=features.kinetic_energy,
            )

            is_vacant = (current_state == RoomState.VACANT)
            baseline_tracker.update(features.variance, is_disturbed=not is_vacant)

            # Predict occupant count
            headcount = crowd_estimator.predict_occupants(features, is_room_vacant=is_vacant)

            if state_changed:
                logger.info(f"[STATE EVENT] Room transitioned to: {current_state.value} | Headcount: {headcount}")

            # Send telemetry to UI via WebSocket
            now = time.time()
            if now - last_broadcast >= broadcast_interval:
                last_broadcast = now
                telemetry = {
                    "timestamp": now,
                    "state": current_state.value,
                    "headcount": headcount,
                    "raw_signal": float(raw_win[-1]),
                    "filtered_signal": float(hampel_win[-1]),
                    "variance": features.variance,
                    "kinetic_energy": features.kinetic_energy,
                    "entropy": features.spectral_entropy,
                }
                asyncio.run_coroutine_threadsafe(ws_manager.broadcast_json(telemetry), loop)


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Launch DSP engine on dedicated worker thread
    dsp_thread = threading.Thread(target=dsp_pipeline_loop, args=(loop,), daemon=True)
    dsp_thread.start()

    # Start FastAPI server on main thread
    config = uvicorn.Config(
        app=app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


if __name__ == "__main__":
    main()
