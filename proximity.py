import json
import pathlib
import time
from collections import deque
import numpy as np


class ProximityDetector:

    def __init__(
        self,
        ref_rssi_at_1m: float = -48.0,
        path_loss_n: float = 3.2,
        history_len: int = 20,
        vector_window_sec: float = 0.8,
    ):
        self.history_len = history_len
        self.vector_window_sec = vector_window_sec

        self.rssi_buffer = deque(maxlen=history_len)
        self.doppler_energy_buffer = deque(maxlen=history_len)
        self.trajectory_buffer = deque(maxlen=35)
        self.smoothed_distance = 1.8

        # Project-anchored profile path
        profile_path = pathlib.Path(__file__).resolve().parent / "profile.json"
        if profile_path.exists():
            try:
                prof = json.loads(profile_path.read_text(encoding="utf-8"))
                self.desk_mean = float(prof.get("desk_mean", -49.07))
                self.away_mean = float(prof.get("away_mean", -38.09))
                self.desk_std = float(prof.get("desk_std", 7.94))
                self.away_std = float(prof.get("away_std", 7.20))
            except Exception:
                self._load_defaults()
        else:
            self._load_defaults()

    def _load_defaults(self):
        self.desk_mean = -49.07
        self.away_mean = -38.09
        self.desk_std = 7.94
        self.away_std = 7.20

    def process(self, raw_rssi: float, filtered_doppler_sample: float) -> dict:
        now = time.time()
        self.rssi_buffer.append(raw_rssi)
        self.doppler_energy_buffer.append(filtered_doppler_sample)

        if len(self.rssi_buffer) < 6:
            return {
                "estimated_distance_m": 1.8,
                "kinetic_energy": 0.0,
                "zone": "CALIBRATING",
                "direction": "STATIONARY",
                "radial_velocity_mps": 0.0,
            }

        # 1. Clean RSSI array (allow wider envelope so body shadow responds instantly)
        raw_arr = np.array(self.rssi_buffer)
        med = float(np.median(raw_arr))
        clean = raw_arr[np.abs(raw_arr - med) <= 18.0]
        if len(clean) < 3:
            clean = raw_arr

        # Fast responsive RSSI (weighted 60% recent average, 40% median)
        recent_mean = float(np.mean(clean[-8:]))
        effective_rssi = (0.60 * recent_mean) + (0.40 * float(np.median(clean)))
        rssi_std = float(np.std(clean))
        kinetic_rms = float(
            np.sqrt(np.mean(np.array(self.doppler_energy_buffer) ** 2))
        )

        # 2. Torso Shadow Interpolation
        # desk_mean = -49.07 dBm (attenuated/shadowed)
        # away_mean = -38.09 dBm (direct open line of sight)
        total_span = max(1.0, abs(self.desk_mean - self.away_mean))
        raw_proximity = (self.away_mean - effective_rssi) / total_span
        raw_proximity = float(np.clip(raw_proximity, 0.0, 1.0))

        # Micro-presence booster: When near desk, even breathing (rssi_std > 0.8)
        # solidifies proximity without needing to swing your arms
        if raw_proximity > 0.35 and rssi_std > 0.8:
            proximity_score = min(1.0, raw_proximity + 0.20)
        else:
            proximity_score = raw_proximity

        # 3. Direct Distance Mapping (0.45m at desk up to 2.6m away)
        target_d = 0.45 + ((1.0 - proximity_score) * 2.05)

        # 4. Asymmetric Smoothing Filter:
        # Snappy approach (alpha=0.45), steady departure (alpha=0.30)
        alpha = 0.45 if target_d < self.smoothed_distance else 0.30
        self.smoothed_distance = round(
            (alpha * target_d) + ((1.0 - alpha) * self.smoothed_distance), 2
        )
        estimated_meters = self.smoothed_distance

        self.trajectory_buffer.append((now, estimated_meters))

        # 5. Responsive Directional Vectoring
        direction = "STATIONARY"
        radial_velocity = 0.0

        while (
            self.trajectory_buffer
            and now - self.trajectory_buffer[0][0] > self.vector_window_sec
        ):
            self.trajectory_buffer.popleft()

        if len(self.trajectory_buffer) >= 4:
            t_first, d_first = self.trajectory_buffer[0]
            t_last, d_last = self.trajectory_buffer[-1]
            dt = t_last - t_first

            if dt > 0.12:
                radial_velocity = round((d_last - d_first) / dt, 2)
                # Sensitive approach / receding thresholds
                if radial_velocity <= -0.08:
                    direction = "APPROACHING"
                elif radial_velocity >= 0.08:
                    direction = "RECEDING"

        # 6. Spatial Zones
        if estimated_meters <= 1.0:
            zone = "IMMEDIATE (At Desk)"
        elif estimated_meters <= 2.2:
            zone = "NEAR (Inside Room)"
        elif estimated_meters <= 3.2:
            zone = "MID (Perimeter / Door)"
        else:
            zone = "FAR (Adjacent Room / Hallway)"

        return {
            "estimated_distance_m": estimated_meters,
            "kinetic_energy": round(kinetic_rms, 3),
            "zone": zone,
            "direction": direction,
            "radial_velocity_mps": radial_velocity,
        }
