"""Inference engine estimating occupant headcount from extracted features."""

import logging
from pathlib import Path
from typing import Optional
import joblib
import numpy as np
from src.analysis.features import FeatureSet

logger = logging.getLogger(__name__)


class CrowdEstimator:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model = None
        self.load_model()

    def load_model(self) -> bool:
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded crowd estimator model from {self.model_path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to load model at {self.model_path}: {e}")
        return False

    def predict_occupants(self, features: FeatureSet, is_room_vacant: bool = False) -> int:
        if is_room_vacant:
            return 0

        # Run model inference if loaded
        if self.model is not None:
            try:
                x = features.to_array().reshape(1, -1)
                predicted = int(self.model.predict(x)[0])
                return max(1, predicted)
            except Exception as e:
                logger.debug(f"Model prediction failed, falling back to heuristic: {e}")

        # Heuristic fallback based on variance and spectral energy
        combined_energy = features.variance + (features.kinetic_energy * 2.0)
        if combined_energy < 0.2:
            return 1
        elif combined_energy < 1.2:
            return 1
        else:
            return 2
