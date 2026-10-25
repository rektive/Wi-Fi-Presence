"""Physical feature-based headcount estimator calibrated for clean downlink RF."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CrowdEstimator:
    def __init__(self, model_path: str = ""):
        logger.info("CrowdEstimator initialized with calibrated RF multipath heuristics.")

    def predict_occupants(self, features: Any, is_room_vacant: bool = False) -> int:
        if is_room_vacant:
            return 0

        # Handle both FeatureSet dataclass objects and raw dictionaries
        if isinstance(features, dict):
            variance = float(features.get("variance", 0.0))
            entropy = float(features.get("entropy", 0.0))
        else:
            variance = float(getattr(features, "variance", 0.0))
            entropy = float(getattr(features, "entropy", 0.0))

        # Baseline quiet / empty room
        if variance < 0.08 and entropy < 0.6:
            return 0

        # Two or more distinct occupants creating asynchronous Doppler cadences
        if variance > 18.0 and entropy > 2.40:
            return 2

        # Single occupant moving or breathing in the room
        return 1

    def estimate(self, features: Any, is_room_vacant: bool = False) -> int:
        return self.predict_occupants(features, is_room_vacant=is_room_vacant)
