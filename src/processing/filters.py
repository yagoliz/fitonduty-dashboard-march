"""Signal processing filters for physiological data.

This module provides Butterworth filters and validation utilities for processing
physiological signals (acceleration, PPG, etc.).
"""

from typing import Union

import numpy as np
import pandas as pd
from scipy.signal import butter, find_peaks, sosfiltfilt


def _validate_filter_params(
    signal: Union[np.ndarray, list], cutoff: float, fs: float, order: int, filter_type: str
) -> np.ndarray:
    """
    Validate common filter parameters.

    Parameters
    ----------
    signal : array-like
        Input signal to be filtered
    cutoff : float
        Cutoff frequency in Hz
    fs : float
        Sampling frequency in Hz
    order : int
        Filter order
    filter_type : str
        Type of filter (for error messages)

    Returns
    -------
    np.ndarray
        Validated signal as numpy array

    Raises
    ------
    ValueError
        If any parameter is invalid or signal is too short
    """
    # Convert to numpy array if needed
    signal = np.asarray(signal)

    # Check signal length
    if len(signal) < 2:
        raise ValueError(
            f"Signal too short for filtering: {len(signal)} samples. Minimum 2 samples required."
        )

    # For very short signals, check scipy limitations
    # sosfiltfilt requires signal length > 3 * ntaps, where ntaps = 2 * order
    min_samples_required = 6 * order + 1  # scipy requirement
    min_samples_recommended = 3 * order  # Quality recommendation

    if len(signal) <= min_samples_required:
        raise ValueError(
            f"Signal too short for order-{order} filter: {len(signal)} samples. "
            f"Minimum required: {min_samples_required + 1} samples. "
            f"Consider using a lower filter order or longer signal."
        )

    if len(signal) < min_samples_recommended * 3:  # More conservative warning
        print(
            f"Signal length ({len(signal)}) is shorter than recommended minimum "
            f"({min_samples_recommended * 3}) for order-{order} filter. Results may contain artifacts."
        )

    # Validate sampling frequency
    if fs <= 0:
        raise ValueError(f"Sampling frequency must be positive, got {fs}")

    # Validate filter order
    if order < 1:
        raise ValueError(f"Filter order must be >= 1, got {order}")

    # Check Nyquist frequency constraints
    nyquist = 0.5 * fs

    if cutoff <= 0:
        raise ValueError(f"Cutoff frequency must be positive, got {cutoff}")

    if cutoff >= nyquist:
        raise ValueError(
            f"Cutoff frequency ({cutoff} Hz) must be less than Nyquist frequency "
            f"({nyquist} Hz) for sampling rate {fs} Hz"
        )

    # Additional check for frequencies very close to Nyquist (can cause numerical issues)
    if cutoff > 0.95 * nyquist:
        raise ValueError(
            f"Cutoff frequency ({cutoff} Hz) is too close to Nyquist frequency "
            f"({nyquist} Hz). Maximum recommended: {0.95 * nyquist:.2f} Hz"
        )

    return np.asarray(signal)


def _validate_bandpass_params(
    signal: Union[np.ndarray, list], lowcut: float, highcut: float, fs: float, order: int
) -> np.ndarray:
    """
    Validate bandpass filter parameters.

    Parameters
    ----------
    signal : array-like
        Input signal
    lowcut : float
        Low cutoff frequency in Hz
    highcut : float
        High cutoff frequency in Hz
    fs : float
        Sampling frequency in Hz
    order : int
        Filter order

    Returns
    -------
    np.ndarray
        Validated signal

    Raises
    ------
    ValueError
        If parameters are invalid
    """
    # First validate common parameters (using lowcut as cutoff)
    signal = _validate_filter_params(signal, lowcut, fs, order, "bandpass")

    # Additional bandpass-specific validations
    if highcut <= 0:
        raise ValueError(f"High cutoff frequency must be positive, got {highcut}")

    if lowcut >= highcut:
        raise ValueError(
            f"Low cutoff frequency ({lowcut}) must be less than high cutoff frequency ({highcut})"
        )

    nyquist = 0.5 * fs
    if highcut >= nyquist:
        raise ValueError(
            f"High cutoff frequency ({highcut} Hz) must be less than Nyquist frequency "
            f"({nyquist} Hz) for sampling rate {fs} Hz"
        )

    if highcut > 0.95 * nyquist:
        raise ValueError(
            f"High cutoff frequency ({highcut} Hz) is too close to Nyquist frequency "
            f"({nyquist} Hz). Maximum recommended: {0.95 * nyquist:.2f} Hz"
        )

    return signal


def highpass_filter(
    s: Union[np.ndarray, list], lowcut: float, fs: float, order: int = 5
) -> np.ndarray:
    """
    Apply a Butterworth highpass filter to the signal.

    Parameters
    ----------
    s : array-like
        The signal to be filtered
    lowcut : float
        The low cutoff frequency of the filter (Hz)
    fs : float
        Sampling frequency of the signal (Hz)
    order : int, optional
        Order of the filter (default: 5)

    Returns
    -------
    np.ndarray
        The filtered signal

    Raises
    ------
    ValueError
        If parameters are invalid or signal is too short
    RuntimeError
        If filter operation fails

    Examples
    --------
    >>> import numpy as np
    >>> data = np.random.randn(100)
    >>> filtered_data = highpass_filter(data, lowcut=0.4, fs=50.0, order=5)
    """
    # Validate parameters and convert signal
    signal = _validate_filter_params(s, lowcut, fs, order, "highpass")

    try:
        nyq = 0.5 * fs
        low = lowcut / nyq
        sos = butter(order, low, btype="highpass", output="sos")
        y = sosfiltfilt(sos, signal)
        return y
    except Exception as e:
        print(f"Error in highpass filter: {str(e)}")
        raise RuntimeError(f"Filter operation failed: {str(e)}") from e


def lowpass_filter(
    s: Union[np.ndarray, list], highcut: float, fs: float, order: int = 5
) -> np.ndarray:
    """
    Apply a Butterworth lowpass filter to the signal.

    Parameters
    ----------
    s : array-like
        The signal to be filtered
    highcut : float
        The high cutoff frequency of the filter (Hz)
    fs : float
        Sampling frequency of the signal (Hz)
    order : int, optional
        Order of the filter (default: 5)

    Returns
    -------
    np.ndarray
        The filtered signal

    Raises
    ------
    ValueError
        If parameters are invalid or signal is too short
    RuntimeError
        If filter operation fails

    Examples
    --------
    >>> import numpy as np
    >>> data = np.random.randn(100)
    >>> filtered_data = lowpass_filter(data, highcut=10.5, fs=50.0, order=5)
    """
    # Validate parameters and convert signal
    signal = _validate_filter_params(s, highcut, fs, order, "lowpass")

    try:
        nyq = 0.5 * fs
        high = highcut / nyq
        sos = butter(order, high, btype="lowpass", output="sos")
        y = sosfiltfilt(sos, signal)
        return y
    except Exception as e:
        print(f"Error in lowpass filter: {str(e)}")
        raise RuntimeError(f"Filter operation failed: {str(e)}") from e


def bandpass_filter(
    s: Union[np.ndarray, list], lowcut: float, highcut: float, fs: float, order: int = 5
) -> np.ndarray:
    """
    Apply a Butterworth bandpass filter to the signal.

    Parameters
    ----------
    s : array-like
        The signal to be filtered
    lowcut : float
        The low cutoff frequency of the filter (Hz)
    highcut : float
        The high cutoff frequency of the filter (Hz)
    fs : float
        Sampling frequency of the signal (Hz)
    order : int, optional
        Order of the filter (default: 5)

    Returns
    -------
    np.ndarray
        The filtered signal

    Raises
    ------
    ValueError
        If parameters are invalid or signal is too short
    RuntimeError
        If filter operation fails

    Examples
    --------
    >>> import numpy as np
    >>> data = np.random.randn(100)
    >>> filtered_data = bandpass_filter(data, lowcut=2.0, highcut=10.5, fs=50.0, order=5)
    """
    # Validate parameters and convert signal
    signal = _validate_bandpass_params(s, lowcut, highcut, fs, order)

    try:
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        sos = butter(order, [low, high], btype="bandpass", output="sos")
        y = sosfiltfilt(sos, signal)
        return y
    except Exception as e:
        print(f"Error in bandpass filter: {str(e)}")
        raise RuntimeError(f"Filter operation failed: {str(e)}") from e


def acceleration_filter(
    acc: pd.DataFrame, fs: float, lowcut: float = 10.0
) -> pd.DataFrame:
    """
    Apply a Butterworth highpass filter to the acceleration signals.

    Parameters
    ----------
    acc : pd.DataFrame
        DataFrame containing acceleration signals with columns 'X', 'Y', 'Z'
    fs : float
        Sampling frequency of the signal (Hz)
    lowcut : float, optional
        The low cutoff frequency of the filter (default: 10.0 Hz)

    Returns
    -------
    pd.DataFrame
        DataFrame with added filtered columns 'Xf', 'Yf', 'Zf'

    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> data = pd.DataFrame({"X": np.random.randn(100), "Y": np.random.randn(100), "Z": np.random.randn(100)})
    >>> filtered_data = acceleration_filter(data, fs=50.0, lowcut=10.0)
    """
    acc["Xf"] = highpass_filter(acc["X"].values, lowcut, fs)
    acc["Yf"] = highpass_filter(acc["Y"].values, lowcut, fs)
    acc["Zf"] = highpass_filter(acc["Z"].values, lowcut, fs)

    return acc


def ppg_filter(
    ppg: pd.DataFrame, fs: float, lowcut: float = 0.3, highcut: float = 4.0
) -> pd.DataFrame:
    """
    Apply a Butterworth bandpass filter to the PPG signals.

    Parameters
    ----------
    ppg : pd.DataFrame
        DataFrame containing PPG signals with columns 'P0', 'P1', 'P2'
    fs : float
        Sampling frequency of the signal (Hz)
    lowcut : float, optional
        The low cutoff frequency of the filter (default: 0.3 Hz)
    highcut : float, optional
        The high cutoff frequency of the filter (default: 4.0 Hz)

    Returns
    -------
    pd.DataFrame
        DataFrame with added filtered columns 'P0f', 'P1f', 'P2f'

    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> data = pd.DataFrame({"P0": np.random.randn(100), "P1": np.random.randn(100), "P2": np.random.randn(100)})
    >>> filtered_data = ppg_filter(data, fs=50.0, lowcut=0.3, highcut=4.0)
    """
    ppg["P0f"] = bandpass_filter(ppg["P0"].values, lowcut, highcut, fs)
    ppg["P1f"] = bandpass_filter(ppg["P1"].values, lowcut, highcut, fs)
    ppg["P2f"] = bandpass_filter(ppg["P2"].values, lowcut, highcut, fs)

    return ppg


def find_peaks_and_minimas_np(mag: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Find peaks and minima in the magnitude data using a custom algorithm.

    This function processes the magnitude data to identify significant peaks and minima,
    which are then used to calculate steps per second.

    Parameters
    ----------
    mag : np.ndarray
        The magnitude data as a NumPy array

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (minima_indices, peaks_indices)
        - minima_indices: Indices of the minima in the magnitude data
        - peaks_indices: Indices of the peaks in the magnitude data
    """
    # Get the minimum points for range of 5
    argmins = [np.argmin(mag[i : i + 5]) + i for i in range(0, mag.shape[0] - 10, 5)]
    argmins_mag = [mag[i] for i in argmins]

    # Find minima in the processed data
    minima, _ = find_peaks(-np.array(argmins_mag).reshape(-1), height=100)

    # Get indices and magnitudes of minima
    minima_indices = np.array(argmins)[minima]
    minima_magnitudes = np.array(argmins_mag)[minima]

    # Find peaks between minima
    peaks_indices = np.array(
        [
            np.argmax(mag[minima_indices[i] : minima_indices[i + 1]]) + minima_indices[i]
            for i in range(len(minima_indices) - 1)
        ]
    )

    return minima_indices, peaks_indices
