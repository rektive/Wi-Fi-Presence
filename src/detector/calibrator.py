"""Records and computes empty-room baseline profiles."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

logger = logging.getLogger(__name__)


class Calibrator:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.samples: List[float] = []

    def record_sample(self, val: float) -> None:
        self.samples.append(val)

    def compute_and_save(self, interface: str, capture_mode: str, fs: int) -> Dict[str, Any]:
        if len(self.samples) < 50:
            raise ValueError(f"Insufficient samples for calibration: {len(self.samples)}")

        data = np.array(self.samples, dtype=np.float64)
        mean_val = float(np.mean(data))
        variance = float(np.var(data))
        std_dev = float(np.std(data))
        q75, q25 = np.percentile(data, [75, 25])
        iqr = float(q75 - q25)
        med = float(np.median(data))
        mad = float(np.median(np.abs(data - med)))
        hampel_thresh = float(3.0 * 1.4826 * mad)

        profile = {
            "calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "interface": interface,
            "capture_mode": capture_mode,
            "sampling_rate_hz": fs,
            "sample_count": len(self.samples),
            "baseline_metrics": {
                "mean_signal": mean_val,
                "variance": variance,
                "std_dev": std_dev,
                "interquartile_range": iqr,
                "hampel_threshold": hampel_thresh,
            },
            "spectral_noise_floor": {
                "kinetic_band_energy_mean": variance * 0.15,
                "kinetic_band_energy_max": variance * 0.45,
            },
            "status": "calibrated",
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)

        logger.info(f"Calibration saved to {self.output_path}")
        return profile
