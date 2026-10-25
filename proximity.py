import math
import time
from collections import deque
import numpy as np


class ProximityDetector:

    def __init__(
        self,
        ref_rssi_at_1m: float = -48.0,
        path_loss_n: float = 3.2,
        history_len: int = 25,
        vector_window_sec: float = 0.8,
    ):
        """ref_rssi_at_1m: Calibrated for downstairs router through floor (-48 dBm).

        path_loss_n: 3.2 indoor wall-partition exponent (attenuates drywall bleed).
        """
        self.ref_rssi = ref_rssi_at_1m
        self.n = path_loss_n
        self.vector_window_sec = vector_window_sec

        self.rssi_buffer = deque(maxlen=history_len)
        self.doppler_energy_buffer = deque(maxlen=history_len)
        self.trajectory_buffer = deque(maxlen=60)

    def process(self, raw_rssi: float, filtered_doppler_sample: float) -> dict:
        now = time.time()
        self.rssi_buffer.append(raw_rssi)
        self.doppler_energy_buffer.append(filtered_doppler_sample**2)

        # 1. Smoothed baseline RSSI via median filter
        median_rssi = float(np.median(self.rssi_buffer))

        # 2. Kinetic perturbation energy (short-term variance)
        kinetic_variance = float(np.var(self.doppler_energy_buffer))

        # 3. Log-distance path approximation with calibrated drywall exponent
        exponent = (self.ref_rssi - median_rssi) / (10.0 * self.n)
        raw_distance = math.pow(10, exponent)

        # 4. Proximity scaling biased by kinetic energy
        if kinetic_variance > 1.2:
            estimated_meters = max(0.25, round(raw_distance * 0.70, 2))
        else:
            estimated_meters = round(raw_distance, 2)

        self.trajectory_buffer.append((now, estimated_meters))

        # 5. Directional Vectoring (Slope / Velocity)
        direction = "STATIONARY"
        radial_velocity = 0.0

        while (
            self.trajectory_buffer
            and now - self.trajectory_buffer[0][0] > self.vector_window_sec
        ):
            self.trajectory_buffer.popleft()

        if len(self.trajectory_buffer) >= 5 and kinetic_variance > 0.3:
            t_first, d_first = self.trajectory_buffer[0]
            t_last, d_last = self.trajectory_buffer[-1]
            dt = t_last - t_first

            if dt > 0.15:
                radial_velocity = round((d_last - d_first) / dt, 2)
                if radial_velocity <= -0.25:
                    direction = "APPROACHING"
                elif radial_velocity >= 0.25:
                    direction = "RECEDING"

        # 6. Spatial Classification
        if estimated_meters <= 0.9 or (
            estimated_meters <= 1.2 and kinetic_variance > 2.0
        ):
            zone = "IMMEDIATE (At Desk)"
        elif estimated_meters <= 2.2:
            zone = "NEAR (Center of Room)"
        elif estimated_meters <= 3.5:
            zone = "MID (Room Perimeter / Door)"
        else:
            zone = "FAR (Adjacent Room / Hallway)"

        return {
            "estimated_distance_m": estimated_meters,
            "kinetic_energy": round(kinetic_variance, 3),
            "zone": zone,
            "direction": direction,
            "radial_velocity_mps": radial_velocity,
        }
