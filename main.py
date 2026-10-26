#!/usr/bin/env python3
"""Main execution entry point: orchestrates capture, DSP pipeline, and ASGI server."""

import asyncio
import atexit
import collections
import json
import logging
import os
import subprocess
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
from proximity import ProximityDetector

ENABLE_PROXIMITY = os.getenv("ENABLE_PROXIMITY", "True").lower() in ("true", "1", "yes")

proximity_detector = ProximityDetector(ref_rssi_at_1m=-48.0, path_loss_n=3.2)
app.state.proximity_tracker = proximity_detector

def _cleanup_pings():
    try:
        subprocess.run(["killall", "-9", "ping"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

atexit.register(_cleanup_pings)

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

    # Automatically illuminate the room with 50 Hz packet stream in monitor mode
    if settings.CAPTURE_MODE == "monitor":
        logger.info(f"Auto-spawning background packet stream to {settings.ROUTER_IP} at 50 Hz...")
        try:
            subprocess.Popen(
                ["ping", "-i", "0.02", settings.ROUTER_IP],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning(f"Could not auto-start illumination ping: {e}")

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

    last_pulse_time = time.time()
    pulse_packet_count = 0
    empty_streak = 0

    while True:
        sample = ingestor.get_sample(timeout=0.1)
        if sample is None:
            empty_streak += 1
            if empty_streak % 30 == 0:
                logger.warning(f"[NO DATA] 0 packets in 3s! Verify that {settings.WIFI_INTERFACE} is on Channel 11.")
            continue

        empty_streak = 0
        _, val = sample
        buffer.append(val)
        pulse_packet_count += 1

        now_pulse = time.time()
        if now_pulse - last_pulse_time >= 1.0:
            rate_hz = pulse_packet_count / max(0.001, (now_pulse - last_pulse_time))
            cur_dist = f"{prox_data['estimated_distance_m']}m" if ('prox_data' in locals() and prox_data.get('estimated_distance_m') is not None) else "calibrating"
            cur_dir = prox_data.get('direction', 'STATIONARY') if 'prox_data' in locals() else "STATIONARY"
            cur_state = current_state.value if 'current_state' in locals() else "INIT"
            logger.info(f"[RADAR PULSE] {rate_hz:.0f} pkts/s | RSSI: {val:.1f} dBm | Dist: {cur_dist} | Dir: {cur_dir} | State: {cur_state}")
            last_pulse_time = now_pulse
            pulse_packet_count = 0

        if len(buffer) >= max(30, settings.WINDOW_SIZE_SAMPLES // 2):
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
            # Compute real-time proximity and distance first
            if ENABLE_PROXIMITY:
                prox_data = proximity_detector.process(float(val), float(filtered_win[-1]))
            else:
                prox_data = {"proximity": "DISABLED", "estimated_distance_m": None, "is_seated": False}

            cur_dist = prox_data.get("estimated_distance_m", 1.0)
            is_seated = prox_data.get("is_seated", False)
            
            # Predict in-room vs total RF targets (filtering through-wall interference)
            in_radius_count, total_detected = crowd_estimator.predict_occupants(
                features,
                is_room_vacant=is_vacant,
                distance_m=cur_dist,
                is_seated=is_seated
            )
            headcount = in_radius_count

            # Compute real-time proximity and distance
            if ENABLE_PROXIMITY:
                prox_data = proximity_detector.process(float(val), float(filtered_win[-1]))
            else:
                prox_data = {"proximity": "DISABLED", "estimated_distance_m": None}

            if state_changed:
                if ENABLE_PROXIMITY and "zone" in prox_data:
                    logger.info(f"[STATE EVENT] Room: {current_state.value} | Headcount: {headcount} | Proximity: {prox_data['zone']} (~{prox_data['estimated_distance_m']}m) | Motion: {prox_data.get('direction', 'STATIONARY')}")
                else:
                    logger.info(f"[STATE EVENT] Room transitioned to: {current_state.value} | Headcount: {headcount}")

            # Send telemetry to UI via WebSocket
            now = time.time()
            if now - last_broadcast >= broadcast_interval:
                last_broadcast = now
                telemetry = {
                    "timestamp": now,
                    "state": current_state.value,
                    "headcount": in_radius_count,
                    "in_radius_headcount": in_radius_count,
                    "total_headcount": total_detected,
                    "through_wall_detected": (total_detected > in_radius_count),
                    "raw_signal": float(raw_win[-1]),
                    "filtered_signal": float(hampel_win[-1]),
                    "variance": features.variance,
                    "kinetic_energy": features.kinetic_energy,
                    "entropy": features.spectral_entropy,
                }
                if ENABLE_PROXIMITY:
                    telemetry.update(prox_data)
                asyncio.run_coroutine_threadsafe(ws_manager.broadcast_json(telemetry), loop)


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    dsp_thread = threading.Thread(target=dsp_pipeline_loop, args=(loop,), daemon=True)
    dsp_thread.start()

    config = uvicorn.Config(
        app=app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    try:
        loop.run_until_complete(server.serve())
    finally:
        _cleanup_pings()


if __name__ == "__main__":
    main()
