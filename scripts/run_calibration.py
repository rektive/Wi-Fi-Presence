#!/usr/bin/env python3
"""CLI tool to record empty-room baseline profile."""

import sys
import time
from pathlib import Path
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings
from src.capture import MonitorSniffer, ActiveProber
from src.detector.calibrator import Calibrator


def main():
    duration_sec = 20
    total_samples = duration_sec * settings.SAMPLING_RATE_HZ

    print("\n" + "=" * 60)
    print("  EMPTY ROOM CALIBRATION WIZARD")
    print("=" * 60)
    print(">> IMPORTANT: Ensure NO ONE is moving in the room or hallway.")
    print(f">> Recording for {duration_sec} seconds (~{total_samples} samples)...\n")

    time.sleep(2)

    if settings.CAPTURE_MODE == "monitor":
        ingestor = MonitorSniffer(settings.WIFI_INTERFACE, settings.ROUTER_BSSID)
    else:
        ingestor = ActiveProber(settings.ROUTER_IP, rate_hz=settings.SAMPLING_RATE_HZ)

    calibrator = Calibrator(settings.BASELINE_STATE_PATH)
    ingestor.start()

    with Progress(
        TextColumn("[bold green]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Calibrating baseline...", total=total_samples)

        while not progress.finished:
            sample = ingestor.get_sample(timeout=0.1)
            if sample:
                _, val = sample
                calibrator.record_sample(val)
                progress.update(task, advance=1)

    ingestor.stop()

    profile = calibrator.compute_and_save(
        interface=settings.WIFI_INTERFACE,
        capture_mode=settings.CAPTURE_MODE,
        fs=settings.SAMPLING_RATE_HZ,
    )

    metrics = profile["baseline_metrics"]
    print("\n[+] Calibration successfully recorded!")
    print(f"    - Baseline Mean:     {metrics['mean_signal']:.4f}")
    print(f"    - Baseline Variance: {metrics['variance']:.6f}")
    print(f"    - Hampel Threshold:  {metrics['hampel_threshold']:.4f}")
    print(f"    - File written:      {settings.BASELINE_STATE_PATH}\n")


if __name__ == "__main__":
    main()
