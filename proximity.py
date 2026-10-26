"""Stabilized Proximity & Distance Tracking Engine with Kinetic Gating and Desk Deadband."""

import math
import time
import numpy as np


class ProximityDetector:
    def __init__(self, ref_rssi_at_1m: float = -48.0, path_loss_n: float = 3.2):
        self.ref_rssi_at_1m = float(ref_rssi_at_1m)
        self.path_loss_n = float(path_loss_n)
        
        # Factory / Default profile anchors
        self.desk_mean = -49.07
        self.away_mean = -38.09
        self.vacant_variance = 0.0412
        self.baseline_rssi = self.away_mean

        # Internal filter states
        self.smoothed_rssi = self.desk_mean
        self.filtered_distance = 0.90
        self.last_raw_rssi = self.desk_mean
        self.last_update_time = time.time()
        
        # Motion & state hysteresis
        self.desk_locked = True
        self.motion_history = []
        self.direction_votes = []
        self.last_valid_direction = "STATIONARY"

    def update_profile(self, desk_mean: float, away_mean: float, ref_rssi: float = None, path_loss_n: float = None, vacant_variance: float = None):
        """Dynamically updates calibration anchors without restarting the server."""
        self.desk_mean = float(desk_mean)
        self.away_mean = float(away_mean)
        self.baseline_rssi = float(away_mean)
        if ref_rssi is not None:
            self.ref_rssi_at_1m = float(ref_rssi)
        if path_loss_n is not None:
            self.path_loss_n = float(path_loss_n)
        if vacant_variance is not None:
            self.vacant_variance = float(vacant_variance)

    def _rssi_to_distance(self, rssi: float) -> float:
        """Computes physical distance using the log-distance path loss model bounded to indoor bounds."""
        exp = (self.ref_rssi_at_1m - rssi) / (10.0 * max(1.2, self.path_loss_n))
        raw_d = math.pow(10.0, exp)
        return max(0.4, min(4.5, raw_d))

    def process(self, raw_rssi: float, doppler_sample: float) -> dict:
        """Processes live packet telemetry with kinetic gating, desk deadband, and adaptive filtering."""
        now = time.time()
        dt = max(0.01, now - self.last_update_time)
        self.last_update_time = now
        self.last_raw_rssi = raw_rssi

        # 1. Kinetic energy evaluation from Doppler bandpass signal
        kinetic_energy = abs(float(doppler_sample))
        self.motion_history.append(kinetic_energy)
        if len(self.motion_history) > 20:
            self.motion_history.pop(0)
        
        avg_kinetic = float(np.mean(self.motion_history)) if self.motion_history else 0.0
        is_actively_moving = avg_kinetic > 0.065

        # 2. Desk Shadow Proximity Evaluation
        # If signal is near desk baseline (-49 dBm) and motion is low, human is seated
        rssi_delta_from_desk = abs(raw_rssi - self.desk_mean)
        
        if not is_actively_moving and rssi_delta_from_desk <= 3.5:
            self.desk_locked = True
        elif is_actively_moving and rssi_delta_from_desk > 5.0:
            self.desk_locked = False

        # 3. Adaptive Dual-Rate Filtering (Kinetic Gating)
        if self.desk_locked:
            # Heavily damped filter while seated to eliminate all carrier jitter
            alpha_rssi = 0.025
            alpha_dist = 0.020
            target_desk_dist = 0.88
            
            # Smoothly attract and lock to desk position
            self.smoothed_rssi = (alpha_rssi * raw_rssi) + ((1.0 - alpha_rssi) * self.smoothed_rssi)
            self.filtered_distance = (alpha_dist * target_desk_dist) + ((1.0 - alpha_dist) * self.filtered_distance)
            
            # Clamp micro-drift inside the desk deadband
            if abs(self.filtered_distance - target_desk_dist) < 0.12:
                self.filtered_distance = target_desk_dist

            zone = "DESK"
            direction = "STATIONARY"

        else:
            # Active movement: dynamic responsiveness to track walking cadence
            alpha_rssi = 0.25 if is_actively_moving else 0.08
            alpha_dist = 0.20 if is_actively_moving else 0.06

            self.smoothed_rssi = (alpha_rssi * raw_rssi) + ((1.0 - alpha_rssi) * self.smoothed_rssi)
            calculated_distance = self._rssi_to_distance(self.smoothed_rssi)
            
            prev_dist = self.filtered_distance
            self.filtered_distance = (alpha_dist * calculated_distance) + ((1.0 - alpha_dist) * self.filtered_distance)

            # 4. Debounced Direction Classification (Avoid flicker)
            velocity = (self.filtered_distance - prev_dist) / dt
            if abs(velocity) < 0.15 or not is_actively_moving:
                vote = "STATIONARY"
            elif velocity < -0.15:
                vote = "APPROACHING"
            else:
                vote = "RECEDING"

            self.direction_votes.append(vote)
            if len(self.direction_votes) > 10:
                self.direction_votes.pop(0)

            # Majority vote prevents single-packet direction flips
            direction = max(set(self.direction_votes), key=self.direction_votes.count)

            # Zone categorization
            if self.filtered_distance <= 1.2:
                zone = "DESK"
            elif self.filtered_distance <= 1.9:
                zone = "MID"
            elif self.filtered_distance <= 2.8:
                zone = "PERIMETER"
            else:
                zone = "AWAY"

        final_distance = round(float(self.filtered_distance), 2)

        return {
            "estimated_distance_m": final_distance,
            "zone": zone,
            "direction": direction,
            "proximity": "ACTIVE",
            "is_seated": self.desk_locked,
            "kinetic_energy": round(avg_kinetic, 4),
            "smoothed_rssi": round(float(self.smoothed_rssi), 2),
            "raw_rssi": round(float(raw_rssi), 2)
        }
