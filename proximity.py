import time
from collections import deque
import numpy as np


class ProximityDetector:

    def __init__(
        self,
        ref_rssi_at_1m: float = -48.0,
        path_loss_n: float = 3.2,
        history_len: int = 35,
        vector_window_sec: float = 0.8,
    ):
        self.history_len = history_len
        self.vector_window_sec = vector_window_sec

        self.rssi_buffer = deque(maxlen=history_len)
        self.doppler_energy_buffer = deque(maxlen=history_len)
        self.trajectory_buffer = deque(maxlen=60)
        self.smoothed_distance = 2.5

    def process(self, raw_rssi: float, filtered_doppler_sample: float) -> dict:
        now = time.time()
        self.rssi_buffer.append(raw_rssi)
        self.doppler_energy_buffer.append(filtered_doppler_sample**2)

        # Wait until buffer has sufficient data points
        if len(self.rssi_buffer) < 15:
            return {
                "estimated_distance_m": 2.5,
                "kinetic_energy": 0.0,
                "zone": "CALIBRATING",
                "direction": "STATIONARY",
                "radial_velocity_mps": 0.0,
            }

        # 1. Perturbation metrics (Peak-to-peak spread & kinetic variance)
        rssi_arr = np.array(self.rssi_buffer)
        p90 = np.percentile(rssi_arr, 90)
        p10 = np.percentile(rssi_arr, 10)
        perturbation_spread = float(p90 - p10)

        kinetic_energy = float(np.mean(self.doppler_energy_buffer))

        # 2. Physics-based Distance Mapping via Multipath Dispersion
        # Intense near-field disruption = Close (<1m)
        # Moderate room reflection = Mid (1.5 - 2.5m)
        # Subdued drywall-attenuated bleed = Far (>3m)
        if kinetic_energy > 80.0 or perturbation_spread > 22.0:
            target_d = 0.45 + max(0.0, (18.0 - min(perturbation_spread, 30.0)) * 0.03)
        elif kinetic_energy > 20.0 or perturbation_spread > 12.0:
            target_d = 1.0 + (22.0 - perturbation_spread) * 0.08
        elif kinetic_energy > 4.0 or perturbation_spread > 5.0:
            target_d = 2.0 + (12.0 - perturbation_spread) * 0.15
        elif kinetic_energy > 0.8 or perturbation_spread > 2.0:
            target_d = 3.2 + (5.0 - perturbation_spread) * 0.25
        else:
            target_d = 4.5

        target_d = max(0.3, min(5.0, round(target_d, 2)))

        # Exponential Moving Average for jitter reduction
        alpha = 0.25
        self.smoothed_distance = round(
            (alpha * target_d) + ((1.0 - alpha) * self.smoothed_distance), 2
        )
        estimated_meters = self.smoothed_distance

        self.trajectory_buffer.append((now, estimated_meters))

        # 3. Directional Vectoring (Slope / Velocity)
        direction = "STATIONARY"
        radial_velocity = 0.0

        while (
            self.trajectory_buffer
            and now - self.trajectory_buffer[0][0] > self.vector_window_sec
        ):
            self.trajectory_buffer.popleft()

        if len(self.trajectory_buffer) >= 6 and kinetic_energy > 2.0:
            t_first, d_first = self.trajectory_buffer[0]
            t_last, d_last = self.trajectory_buffer[-1]
            dt = t_last - t_first

            if dt > 0.15:
                radial_velocity = round((d_last - d_first) / dt, 2)
                if radial_velocity <= -0.25:
                    direction = "APPROACHING"
                elif radial_velocity >= 0.25:
                    direction = "RECEDING"

        # 4. Spatial Zone Classification
        if estimated_meters <= 0.9:
            zone = "IMMEDIATE (At Desk)"
        elif estimated_meters <= 2.2:
            zone = "NEAR (Center of Room)"
        elif estimated_meters <= 3.5:
            zone = "MID (Room Perimeter / Door)"
        else:
            zone = "FAR (Adjacent Room / Hallway)"

        return {
            "estimated_distance_m": estimated_meters,
            "kinetic_energy": round(kinetic_energy, 3),
            "zone": zone,
            "direction": direction,
            "radial_velocity_mps": radial_velocity,
        }
