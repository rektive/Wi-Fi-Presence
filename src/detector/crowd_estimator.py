"""Advanced Crowd Estimation with Geofence Gating and Multipath Wall Isolation."""

import numpy as np


class CrowdEstimator:
    def __init__(self, model_path=None):
        self.baseline_var = 0.0412
        self.baseline_kin = 0.045
        self.max_room_radius_m = 2.5  # Boundary threshold (meters)

    def update_baseline(self, var: float, kin: float):
        """Dynamically tunes ambient clutter references from active room profile."""
        self.baseline_var = max(0.005, float(var))
        self.baseline_kin = max(0.005, float(kin))

    def predict_occupants(self, features, is_room_vacant: bool = False, distance_m: float = 1.0, is_seated: bool = False) -> tuple[int, int]:
        """
        Calculates occupancy with strict perimeter geofencing.
        Returns: (in_radius_count, total_rf_detected)
        """
        if is_room_vacant:
            return 0, 0

        var = float(features.variance)
        kin = float(features.kinetic_energy)

        # 1. Evaluate total macroscopic disturbance across the entire RF environment
        # Realistic multi-person thresholds:
        # 1 person walking: kin 0.2 - 1.5 RMS, var 0.15 - 0.6
        # 2 people moving:  kin 1.8 - 3.5 RMS, var 0.8 - 2.5 (cross-multipath constructive interference)
        # 3+ people moving: kin > 3.8 RMS,     var > 3.0
        if kin > 3.8 or var > 3.0:
            total_detected = 3
        elif kin > 1.8 or var > 0.85:
            total_detected = 2
        else:
            total_detected = 1

        # 2. Wall Isolation & Distance Geofence Gating
        # If the primary calculated RF reflection distance is outside the room perimeter (>2.5m),
        # the motion is originating from the adjacent room through the drywall.
        if distance_m is not None and distance_m > self.max_room_radius_m:
            # Person is behind the wall; in-room presence remains at seated/base count
            in_radius = 1 if is_seated else 0
        else:
            # Motion is physically inside the room boundary
            in_radius = total_detected

        return in_radius, total_detected
