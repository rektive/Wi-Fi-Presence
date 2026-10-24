"""Time-domain and frequency-domain feature engineering pipeline."""

from dataclasses import dataclass, asdict
from typing import Dict, Any
import numpy as np
from scipy import stats
from src.analysis.doppler import compute_spectral_energy


@dataclass
class FeatureSet:
    variance: float
    std_dev: float
    iqr: float
    skewness: float
    kurtosis: float
    kinetic_energy: float
    spectral_entropy: float

    def to_array(self) -> np.ndarray:
        return np.array([
            self.variance,
            self.std_dev,
            self.iqr,
            self.skewness,
            self.kurtosis,
            self.kinetic_energy,
            self.spectral_entropy,
        ], dtype=np.float32)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def extract_feature_vector(raw_window: np.ndarray, filtered_window: np.ndarray, fs: float = 50.0) -> FeatureSet:
    """Extracts a unified feature set from sliding temporal signal windows."""
    var = float(np.var(raw_window))
    std = float(np.std(raw_window))

    # Interquartile Range (IQR)
    q75, q25 = np.percentile(raw_window, [75, 25])
    iqr = float(q75 - q25)

    # Higher-order statistical moments
    skew = float(stats.skew(raw_window)) if len(raw_window) > 2 else 0.0
    kurt = float(stats.kurtosis(raw_window)) if len(raw_window) > 2 else 0.0

    # Frequency-domain Doppler metrics
    energy, entropy = compute_spectral_energy(filtered_window, fs=fs)

    return FeatureSet(
        variance=var,
        std_dev=std,
        iqr=iqr,
        skewness=skew,
        kurtosis=kurt,
        kinetic_energy=energy,
        spectral_entropy=entropy,
    )
