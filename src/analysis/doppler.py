"""Short-Time Fourier Transform (STFT) and kinetic Doppler energy extraction."""

from typing import Tuple
import numpy as np
from scipy import signal


def compute_spectral_energy(
    filtered_data: np.ndarray,
    fs: float = 50.0,
    kinetic_low: float = 1.0,
    kinetic_high: float = 3.5,
) -> Tuple[float, float]:
    """
    Computes human walking cadence energy (1.0 - 3.5 Hz) and spectral entropy.
    Returns: (kinetic_band_energy, spectral_entropy)
    """
    if len(filtered_data) < 16:
        return 0.0, 0.0

    freqs, psd = signal.welch(filtered_data, fs=fs, nperseg=min(len(filtered_data), 64))

    # Mask frequencies within walking Doppler band
    band_mask = (freqs >= kinetic_low) & (freqs <= kinetic_high)
    band_energy = float(np.sum(psd[band_mask]))

    # Calculate Spectral Entropy (measure of multi-path scatterer complexity)
    psd_norm = psd / (np.sum(psd) + 1e-12)
    entropy = -np.sum(psd_norm * np.log2(psd_norm + 1e-12))

    return band_energy, float(entropy)
