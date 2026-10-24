"""Adaptive baseline and environmental drift tracker using Exponential Moving Averages."""

from typing import Tuple
import numpy as np


class DynamicBaseline:
    def __init__(self, alpha: float = 0.005, initial_mean: float = 0.0, initial_variance: float = 0.05):
        self.alpha = alpha
        self.mean = initial_mean
        self.variance = initial_variance
        self.is_initialized = False

    def initialize(self, calibration_data: np.ndarray) -> None:
        """Sets the starting conditions from a calibrated empty-room capture."""
        if len(calibration_data) > 0:
            self.mean = float(np.mean(calibration_data))
            self.variance = float(np.var(calibration_data))
            self.is_initialized = True

    def update(self, current_sample: float, is_disturbed: bool = False) -> Tuple[float, float]:
        """
        Updates running metrics. If human movement is actively detected,
        the update rate is frozen to prevent learning human presence as the baseline.
        """
        if not self.is_initialized:
            self.mean = current_sample
            self.variance = 0.05
            self.is_initialized = True
            return self.mean, self.variance

        if not is_disturbed:
            diff = current_sample - self.mean
            self.mean += self.alpha * diff
            self.variance = (1.0 - self.alpha) * self.variance + self.alpha * (diff**2)

        return self.mean, self.variance
