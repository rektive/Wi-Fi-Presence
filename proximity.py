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
        history_len: int = 25,
        vector_window_sec: float = 0.9,
    ):
        self.history_len = history_len
        self.vector_window_sec = vector_window_sec

        self.rssi_buffer = deque(maxlen=history_len)
        self.doppler_energy_buffer = deque(maxlen=history_len)
        self.trajectory_buffer = deque(maxlen=40)
        self.smoothed_distance = 1.8

        # Anchor path to the actual project folder, safe under sudo
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

        if len(self.rssi_buffer) < 8:
            return {
                "estimated_distance_m": 1.8,
                "kinetic_energy": 0.0,
                "zone": "CALIBRATING",
                "direction": "STATIONARY",
                "radial_velocity_mps": 0.0,
            }

        # 1. Clean RSSI array (outlier rejection)
        raw_arr = np.array(self.rssi_buffer)
        med = float(np.median(raw_arr))
        clean = raw_arr[np.abs(raw_arr - med) <= 14.0]
        if len(clean) < 4:
            clean = raw_arr

        current_median = float(np.median(clean))
        kinetic_rms = float(
            np.sqrt(np.mean(np.array(self.doppler_energy_buffer) ** 2))
        )

        # 2. Torso Shadow Mapping (Interpolation between Desk and Away)
        # desk_mean = -49.07 dBm (heavy shadow)
        # away_mean = -38.09 dBm (unobstructed line of sight)
        # Ratio: 1.0 = Desk, 0.0 = 2.5m Away
        total_span = abs(self.desk_mean - self.away_mean)
        desk_proximity = (self.away_mean - current_median) / total_span
        desk_proximity = float(np.clip(desk_proximity, 0.0, 1.0))

        # 3. Direct Distance Mapping (0.5m at desk to 2.6m away)
        # When desk_proximity is 1.0 -> 0.50m
        # When desk_proximity is 0.0 -> 2.50m
        target_d = 0.50 + ((1.0 - desk_proximity) * 2.00)

        # 4. Asymmetric Smoothing Filter
        alpha = 0.35 if target_d > self.smoothed_distance else 0.25
        self.smoothed_distance = round(
            (alpha * target_d) + ((1.0 - alpha) * self.smoothed_distance), 2
        )
        estimated_meters = self.smoothed_distance

        self.trajectory_buffer.append((now, estimated_meters))

        # 5. Directional Vectoring
        direction = "STATIONARY"
        radial_velocity = 0.0

        while (
            self.trajectory_buffer
            and now - self.trajectory_buffer[0][0] > self.vector_window_sec
        ):
            self.trajectory_buffer.popleft()

        if len(self.trajectory_buffer) >= 5 and kinetic_rms > 0.4:
            t_first, d_first = self.trajectory_buffer[0]
            t_last, d_last = self.trajectory_buffer[-1]
            dt = t_last - t_first

            if dt > 0.15:
                radial_velocity = round((d_last - d_first) / dt, 2)
                if radial_velocity <= -0.15:
                    direction = "APPROACHING"
                elif radial_velocity >= 0.15:
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
