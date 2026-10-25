import time
from collections import deque
import numpy as np


class ProximityDetector:

    def __init__(
        self,
        ref_rssi_at_1m: float = -48.0,
        path_loss_n: float = 3.2,
        history_len: int = 30,
        vector_window_sec: float = 0.9,
    ):
        self.ref_baseline = ref_rssi_at_1m
        self.history_len = history_len
        self.vector_window_sec = vector_window_sec

        self.rssi_buffer = deque(maxlen=history_len)
        self.doppler_energy_buffer = deque(maxlen=history_len)
        self.trajectory_buffer = deque(maxlen=45)
        self.smoothed_distance = 2.5

    def process(self, raw_rssi: float, filtered_doppler_sample: float) -> dict:
        now = time.time()
        self.rssi_buffer.append(raw_rssi)
        self.doppler_energy_buffer.append(filtered_doppler_sample)

        if len(self.rssi_buffer) < 10:
            return {
                "estimated_distance_m": 2.5,
                "kinetic_energy": 0.0,
                "zone": "CALIBRATING",
                "direction": "STATIONARY",
                "radial_velocity_mps": 0.0,
            }

        # 1. Clean RSSI array (rejection of corrupted frames)
        raw_arr = np.array(self.rssi_buffer)
        med = float(np.median(raw_arr))
        clean = raw_arr[np.abs(raw_arr - med) <= 12.0]
        if len(clean) < 4:
            clean = raw_arr

        median_rssi = float(np.median(clean))
        rssi_std = float(np.std(clean))
        kinetic_rms = float(np.sqrt(np.mean(np.array(self.doppler_energy_buffer) ** 2)))

        # 2. Physics-Based Distance Mapping
        # Torso Shadowing: difference between clean baseline (-48 dBm) and current median
        shadow_attenuation = max(0.0, self.ref_baseline - median_rssi)

        if shadow_attenuation >= 4.0 or (shadow_attenuation >= 2.0 and rssi_std > 1.2):
            # Direct line-of-sight blockage: occupant is sitting/standing directly at desk
            target_d = 0.45 + max(0.0, (10.0 - shadow_attenuation) * 0.06)
        elif rssi_std >= 0.70 or kinetic_rms >= 1.2:
            # Unblocked direct path, but high multipath reflection: moving in room (1.2m - 2.4m)
            target_d = 1.30 + max(0.0, (1.8 - rssi_std) * 1.1)
        elif rssi_std >= 0.25 or kinetic_rms >= 0.40:
            # Distant movement (standing back at 2.5m+ or doorway)
            target_d = 2.50 + max(0.0, (0.70 - rssi_std) * 2.2)
        else:
            # Faint background noise / adjacent room through drywall
            target_d = 3.80 + max(0.0, (0.25 - rssi_std) * 2.5)

        target_d = float(np.clip(target_d, 0.4, 4.5))

        # 3. Dynamic Smoothing Filter (Asymmetric: faster tracking when stepping back)
        alpha = 0.40 if target_d > self.smoothed_distance else 0.25
        self.smoothed_distance = round(
            (alpha * target_d) + ((1.0 - alpha) * self.smoothed_distance), 2
        )
        estimated_meters = self.smoothed_distance

        self.trajectory_buffer.append((now, estimated_meters))

        # 4. Directional Vectoring (Computed across trajectory window)
        direction = "STATIONARY"
        radial_velocity = 0.0

        while (
            self.trajectory_buffer
            and now - self.trajectory_buffer[0][0] > self.vector_window_sec
        ):
            self.trajectory_buffer.popleft()

        if len(self.trajectory_buffer) >= 6:
            t_first, d_first = self.trajectory_buffer[0]
            t_last, d_last = self.trajectory_buffer[-1]
            dt = t_last - t_first

            if dt > 0.18:
                radial_velocity = round((d_last - d_first) / dt, 2)
                # Negative = moving toward antenna; Positive = moving away
                if radial_velocity <= -0.15:
                    direction = "APPROACHING"
                elif radial_velocity >= 0.15:
                    direction = "RECEDING"

        # 5. Zone Classification
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
