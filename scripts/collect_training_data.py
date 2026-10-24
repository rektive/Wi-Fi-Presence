#!/usr/bin/env python3
"""CLI utility to collect labeled training data for headcount model training."""

import argparse
import sys
import time
from pathlib import Path
import numpy as np
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings
from src.capture import MonitorSniffer, ActiveProber
from src.processing.filters import hampel_filter, butterworth_bandpass
from src.analysis.features import extract_feature_vector


def main():
    parser = argparse.ArgumentParser(description="Collect labeled presence datasets.")
    parser.add_argument("--occupants", type=int, required=True, help="Number of occupants in room (e.g. 0, 1, 2)")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds (default: 60)")
    args = parser.parse_args()

    occupants = args.occupants
    duration = args.duration
    target_samples = duration * settings.SAMPLING_RATE_HZ

    print(f"\n[*] Collecting training session: {occupants} occupant(s) for {duration} seconds.")
    print("[*] Perform natural movements (or keep room still if 0 occupants)...")
    time.sleep(2)

    if settings.CAPTURE_MODE == "monitor":
        ingestor = MonitorSniffer(settings.WIFI_INTERFACE, settings.ROUTER_BSSID)
    else:
        ingestor = ActiveProber(settings.ROUTER_IP, rate_hz=settings.SAMPLING_RATE_HZ)

    ingestor.start()

    raw_samples = []
    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Recording {occupants} people...", total=target_samples)

        while not progress.finished:
            sample = ingestor.get_sample(timeout=0.1)
            if sample:
                raw_samples.append(sample[1])
                progress.update(task, advance=1)

    ingestor.stop()

    # Process sliding windows into feature rows
    arr = np.array(raw_samples, dtype=np.float32)
    win_size = settings.WINDOW_SIZE_SAMPLES
    step = win_size // 4

    features = []
    for start_idx in range(0, len(arr) - win_size, step):
        window = arr[start_idx : start_idx + win_size]
        hampel_win = hampel_filter(window, window_size=settings.HAMPEL_WINDOW, n_sigmas=settings.HAMPEL_N_SIGMA)
        filtered_win = butterworth_bandpass(
            hampel_win,
            lowcut=settings.BANDPASS_LOW_HZ,
            highcut=settings.BANDPASS_HIGH_HZ,
            fs=settings.SAMPLING_RATE_HZ,
            order=settings.BUTTERWORTH_ORDER,
        )
        feats = extract_feature_vector(hampel_win, filtered_win, fs=settings.SAMPLING_RATE_HZ)
        features.append(feats.to_array())

    if not features:
        print("[-] Insufficient data collected.")
        return

    X = np.array(features, dtype=np.float32)
    y = np.full((len(features),), occupants, dtype=np.int32)

    ts = int(time.time())
    x_out = settings.DATA_PROCESSED_DIR / f"features_{occupants}p_{ts}.npy"
    y_out = settings.DATA_PROCESSED_DIR / f"labels_{occupants}p_{ts}.npy"

    np.save(x_out, X)
    np.save(y_out, y)

    print(f"\n[+] Saved {len(features)} feature frames to:")
    print(f"    - {x_out}")
    print(f"    - {y_out}\n")


if __name__ == "__main__":
    main()
