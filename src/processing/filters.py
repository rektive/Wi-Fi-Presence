"""DSP filtering algorithms: Hampel, Butterworth bandpass, moving median."""

import numpy as np
from scipy import signal


def hampel_filter(data: np.ndarray, window_size: int = 7, n_sigmas: float = 3.0) -> np.ndarray:
    """Removes single-packet outlier spikes without adding phase lag."""
    n = len(data)
    if n < window_size:
        return data.copy()

    filtered = data.copy()
    k = window_size // 2

    for i in range(k, n - k):
        window = data[i - k : i + k + 1]
        med = np.median(window)
        mad = np.median(np.abs(window - med))
        threshold = n_sigmas * 1.4826 * mad
        if np.abs(data[i] - med) > threshold:
            filtered[i] = med

    return filtered


def butterworth_bandpass(
    data: np.ndarray,
    lowcut: float = 0.3,
    highcut: float = 5.0,
    fs: float = 50.0,
    order: int = 4,
) -> np.ndarray:
    """Isolates human kinetic Doppler frequencies (0.3 Hz to 5.0 Hz)."""
    if len(data) < (order * 3):
        return data - np.mean(data)

    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist

    sos = signal.butter(order, [low, high], btype="bandpass", output="sos")
    filtered = signal.sosfiltfilt(sos, data - np.mean(data))
    return filtered


def moving_median(data: np.ndarray, window_size: int = 5) -> np.ndarray:
    """Standard rolling median smoother."""
    if len(data) < window_size:
        return data
    pad_width = window_size // 2
    padded = np.pad(data, pad_width, mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, window_size)
    return np.median(windows, axis=1)
